import re

from fastapi import APIRouter, Depends, Header, HTTPException, status, Request
from fastapi.responses import Response

from app.core.rate_limit import limiter

from app.database.mongodb import colleges_async_collection, registrations_async_collection, async_db
from app.models.schemas import (
    DuplicateCheck,
    RegistrationSummaryResponse,
    StudentRegister,
    StudentResponse,
)
from app.services.challenge_service import get_registration_summary

from app.services.receipt_service import build_receipt_pdf, verify_receipt_token
from app.services.registration_service import register_student as register_student_service
from config.settings import get_settings

router = APIRouter(tags=["students"])
settings = get_settings()

# Simple email regex for path-parameter validation (B-02)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# Fix C-03: Admin API key dependency
async def require_admin_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    """Protect admin-only endpoints with a shared API key header.
    Set ADMIN_API_KEY in .env to enable. Generate a strong random key with:
        python -c "import secrets; print(secrets.token_urlsafe(32))"
    """
    if not settings.admin_api_key or settings.admin_api_key == "change-this-admin-key":
        raise HTTPException(
            status_code=503,
            detail="Admin API key is not configured on this server. Set ADMIN_API_KEY in .env.",
        )
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-Admin-Key header.",
        )


async def resolve_college_name(student: StudentRegister) -> str:
    selected_college = (student.collegeName or "").strip()
    if not selected_college:
        raise HTTPException(status_code=400, detail="College selection is required")

    if selected_college.lower() == "other":
        manual_college = (student.otherCollegeName or "").strip().lower()
        if not manual_college:
            raise HTTPException(status_code=400, detail="Please enter your college name when selecting Other")
        return manual_college

    existing = await colleges_async_collection.find_one(
        {"name_lc": selected_college.lower()},
        {"_id": 0, "name": 1},
    )
    if not existing:
        raise HTTPException(
            status_code=400,
            detail=f"College '{selected_college}' not found. Please select 'Other' to enter it manually.",
        )
    return existing["name"]


@router.get("/api/check-email/{email:path}")
@limiter.limit("20/minute")
async def check_email_exists(request: Request, email: str):
    email = email.lower().strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    existing = await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"email": email},
                {"leader.email": email},
                {"team_members.email": email},
            ],
        },
        {"_id": 1},
    )
    if existing:
        return {"exists": True, "message": "Email already exists in the system."}
    return {"exists": False}


@router.get("/api/check-rollnumber/{roll_number:path}")
@limiter.limit("20/minute")
async def check_roll_number_exists(request: Request, roll_number: str):
    existing = await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"rollNumber": roll_number},
                {"leader.rollNumber": roll_number},
                {"team_members.rollNumber": roll_number},
            ],
        },
        {"_id": 1},
    )
    if existing:
        return {"exists": True, "message": "Already exists."}
    return {"exists": False}


@router.get("/api/check-github/{github_profile:path}")
@limiter.limit("20/minute")
async def check_github_exists(request: Request, github_profile: str):
    existing = await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"githubProfile": github_profile},
                {"leader.githubProfile": github_profile},
                {"team_members.githubProfile": github_profile},
            ],
        },
        {"_id": 1},
    )
    if existing:
        return {"exists": True, "message": "Already exists."}
    return {"exists": False}


@router.post("/api/check-duplicate")
@limiter.limit("10/minute")
async def check_duplicate(request: Request, data: DuplicateCheck):
    checks = []
    
    if data.email and await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"email": data.email.lower()},
                {"leader.email": data.email.lower()},
                {"team_members.email": data.email.lower()},
            ],
        },
        {"_id": 1},
    ):
        checks.append({"field": "email", "exists": True, "message": "Already exists."})

    if data.rollNumber and await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"rollNumber": data.rollNumber},
                {"leader.rollNumber": data.rollNumber},
                {"team_members.rollNumber": data.rollNumber},
            ],
        },
        {"_id": 1},
    ):
        checks.append({"field": "rollNumber", "exists": True, "message": "Already exists."})

    if data.githubProfile and await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"githubProfile": data.githubProfile},
                {"leader.githubProfile": data.githubProfile},
                {"team_members.githubProfile": data.githubProfile},
            ],
        },
        {"_id": 1},
    ):
        checks.append({"field": "githubProfile", "exists": True, "message": "Already exists."})

    if data.mobile and await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"mobile": data.mobile},
                {"leader.phone": data.mobile},
                {"team_members.mobile": data.mobile},
            ],
        },
        {"_id": 1},
    ):
        checks.append({"field": "mobile", "exists": True, "message": "This mobile number is already registered."})

    return {"hasDuplicate": len(checks) > 0, "duplicates": checks}


@router.post("/api/register", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def register_student(student: StudentRegister):
    settings_doc = await async_db["settings"].find_one()
    if settings_doc and settings_doc.get("registrationOpen") is False:
        raise HTTPException(status_code=403, detail="Registrations are currently closed.")

    resolved_college_name = await resolve_college_name(student)
    student = student.model_copy(update={"collegeName": resolved_college_name})

    if not student.rzp_order_id:
        raise HTTPException(status_code=400, detail="Payment details are missing. Please complete the payment first.")

    db_registration = await registrations_async_collection.find_one(
        {"rzp_order_id": student.rzp_order_id},
        {"_id": 0, "payment": 1}
    )
    if not db_registration or not db_registration.get("payment"):
        raise HTTPException(status_code=400, detail="Payment not found for the given order.")

    payment_data = db_registration.get("payment", {})
    payment_status = str(payment_data.get("status", "")).lower()
    if payment_status not in ["success", "paid", "captured"]:
        raise HTTPException(status_code=400, detail=f"Payment is not successful. Current status: {payment_status}")

    rzp_payment_id = payment_data.get("transaction_id") or student.rzp_payment_id

    return await register_student_service(student, rzp_payment_id, payment_status)


@router.get("/api/registration/{registration_id}/summary", response_model=RegistrationSummaryResponse)
async def registration_summary(registration_id: str):
    return await get_registration_summary(registration_id)


# Fix C-03: Protect /api/all-users-json with admin authentication
@router.get("/api/all-users-json", dependencies=[Depends(require_admin_key)])
async def get_all_users_json():
    """
    Export all registrations as a flat JSON list.
    Requires X-Admin-Key header matching ADMIN_API_KEY env variable.
    """
    cursor = registrations_async_collection.find({"registrationCompleted": True})
    registrations = await cursor.to_list(length=1000)

    flattened_users = []
    for reg in registrations:
        # Participation Mode
        mode = reg.get("participationMode", "individual")

        # Base data from registration
        common_data = {
            "registrationId": reg.get("rzp_order_id"),
            "participationMode": mode,
            "teamId": reg.get("team_id"),
            "teamName": reg.get("team_name"),
            "projectSelected": reg.get("project_selected"),
            "is_reviewed": reg.get("is_reviewed", False),
            "is_selected": reg.get("is_selected", False),
            "reviewed_by": reg.get("Reviewedby"),  # renamed field (L-01)
            "user_feedback": reg.get("user_feedback"),
            "registeredAt": reg.get("registeredAt"),
            "paymentStatus": reg.get("payment_status"),
        }

        # Leader data
        leader = reg.get("leader", {})
        leader_entry = {
            **common_data,
            "role": "leader" if mode == "team" else "individual",
            "participantId": leader.get("participant_id"),
            "fullName": leader.get("name"),
            "email": leader.get("email"),
            "mobile": leader.get("phone"),
            "collegeName": leader.get("college"),
            "branch": leader.get("branch"),
            "city": leader.get("city"),
            "rollNumber": leader.get("rollNumber"),
            "githubProfile": leader.get("githubProfile"),
        }
        flattened_users.append(leader_entry)

        # Team members data
        for member in reg.get("team_members", []):
            member_entry = {
                **common_data,
                "role": "member",
                "participantId": member.get("participant_id"),
                "fullName": member.get("name"),
                "email": member.get("email"),
                "mobile": member.get("mobile"),
                "collegeName": leader.get("college"),  # members share leader's college in current schema
                "branch": member.get("branch") or leader.get("branch"),
                "city": leader.get("city"),
                "rollNumber": member.get("rollNumber"),
                "githubProfile": member.get("githubProfile"),
            }
            flattened_users.append(member_entry)

    return flattened_users


@router.get("/api/receipt/{registration_id}")
async def download_receipt(registration_id: str, email: str, token: str):
    if not verify_receipt_token(token=token, registration_id=registration_id, email=email):
        raise HTTPException(status_code=403, detail="Invalid receipt token")

    registration = await registrations_async_collection.find_one({"rzp_order_id": registration_id})
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    leader_email = str(registration.get("leader", {}).get("email", "")).lower()
    member_emails = {str(item.get("email", "")).lower() for item in registration.get("team_members", [])}
    requested_email = email.lower()
    if requested_email != leader_email and requested_email not in member_emails:
        raise HTTPException(status_code=403, detail="Email is not authorized for this receipt")

    pdf_data = build_receipt_pdf(registration, requested_email)
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Spheronix_Receipt_{registration_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )