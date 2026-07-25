import asyncio
import logging
import secrets
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.core.time_utils import ist_now, utc_now
from app.database.mongodb import registrations_async_collection, teams_async_collection, users_async_collection
from app.models.schemas import StudentRegister, StudentResponse
from app.services.challenge_service import assign_random_challenge
from app.services.receipt_service import build_receipt_download_url, build_receipt_pdf, format_datetime_ist
from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

MIN_TEAM_TOTAL_MEMBERS = 2
MAX_TEAM_TOTAL_MEMBERS = 5
MAX_TEAM_MEMBERS_EXCLUDING_LEADER = 4
from app.services.settings_service import get_registration_fee


def numeric_6() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


async def generate_unique_individual_id() -> str:
    # Fix H-04: Use collision-resistant hex string instead of infinite DB busy-wait loop
    return f"SPX_HACK2026_INDV_{secrets.token_hex(4).upper()}"


async def generate_unique_team_id() -> str:
    # Fix H-04: Use collision-resistant hex string instead of infinite DB busy-wait loop
    return f"SPX_HACK2026_TEAM_{secrets.token_hex(4).upper()}"


def build_team_member_participant_id(team_id: str, member_index: int) -> str:
    return f"{team_id}_{member_index:02d}"


def _build_email_bodies(
    participant_name: str,
    role_text: str,
    participant_id: str,
    team_name: Optional[str],
    team_id: Optional[str],
    task_selected: str,
    assigned_challenge: Dict[str, Any],
    transaction_id: str,
    amount: float,
    currency: str,
    payment_status: str,
    paid_date: str,
    receipt_url: str,
) -> tuple[str, str]:
    team_line = f"Team Name: {team_name}\n" if team_name else ""
    team_id_line = f"Team ID: {team_id}\n" if team_id else ""
    task_line = f"Challenge Category: {task_selected}\n" if task_selected else ""
    task_html = f"<strong>Challenge Category:</strong> {task_selected}<br/>" if task_selected else ""
    challenge_title = str(assigned_challenge.get("title") or "").strip()
    challenge_description = str(assigned_challenge.get("description") or "").strip()
    # challenge_block removed per requirement to hide question from user
    challenge_block = ""
    display_role = role_text.title()

    plain_body = (
        f"Dear {participant_name},\n\n"
        "Thank you for completing your registration for the Spheronix Hackathon 2026.\n"
        "Your payment has been successfully processed, and your participation is now officially confirmed.\n\n"
        "--- Registration Details ---\n"
        f"Role: {display_role}\n"
        f"Participant ID: {participant_id}\n"
        f"{team_line}"
        f"{team_id_line}"
        f"{task_line}"
        f"{challenge_block}"
        f"Transaction ID: {transaction_id}\n"
        f"Amount Paid: {currency} {amount:.2f}\n"
        f"Payment Status: {payment_status}\n"
        f"Payment Date: {paid_date}\n\n"
        "A formal PDF payment receipt is attached to this email for your records.\n"
        f"You may also securely download it here: {receipt_url}\n\n"
        "If you have any questions, please contact our support team at spheronixhackathon@gmail.com.\n\n"
        "Best regards,\n"
        "Spheronix Hackathon Team\n"
        "This is an automated transactional email."
    )

    
    # challenge_html removed per requirement to hide question from user
    challenge_html = ""

    html_body = f"""
        <html>
            <body style="margin:0;padding:0;background:#eef2ff;">
                <span style="display:none;visibility:hidden;opacity:0;color:transparent;height:0;width:0;overflow:hidden;">
                    Registration confirmed. Your hackathon details and payment receipt are securely attached.
                </span>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef2ff;padding:24px 12px;">
                    <tr>
                        <td align="center">
                            <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border-radius:14px;overflow:hidden;border:1px solid #dbe3ff;">
                                <tr>
                                    <td style="background:#173f97;color:#ffffff;padding:20px 24px;">
                                        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:22px;font-weight:700;">Spheronix Hackathon 2026</div>
                                        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:13px;opacity:0.9;margin-top:4px;">Official Registration Confirmation</div>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:24px;">
                                        <p style="margin:0 0 12px 0;font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#111827;">Dear {participant_name},</p>
                                        <p style="margin:0 0 18px 0;font-family:Segoe UI,Arial,sans-serif;font-size:15px;line-height:1.6;color:#374151;">Thank you for registering. Your <strong>{display_role}</strong> registration has been successfully processed, and your spot in the hackathon is officially secured.</p>

                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8faff;border:1px solid #d9e4ff;border-radius:10px;">
                                            <tr><td style="padding:16px 18px;font-family:Segoe UI,Arial,sans-serif;color:#111827;font-size:14px;line-height:1.7;">
                                                <strong>Participant ID:</strong> {participant_id}<br/>
                                                {f'<strong>Team Name:</strong> {team_name}<br/>' if team_name else ''}
                                                {f'<strong>Team ID:</strong> {team_id}<br/>' if team_id else ''}
                                                {task_html}
                                                <strong>Transaction ID:</strong> {transaction_id}<br/>
                                                <strong>Amount Paid:</strong> {currency} {amount:.2f}<br/>
                                                <strong>Payment Status:</strong> {payment_status}<br/>
                                                <strong>Date Processed:</strong> {paid_date}
                                            </td></tr>
                                        </table>

                                        {challenge_html}

                                        <p style="margin:18px 0 14px 0;font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#4b5563;">A formal signed PDF receipt is attached to this email for your records.</p>
                                        <a href="{receipt_url}" style="display:inline-block;background:#173f97;color:#ffffff;text-decoration:none;font-family:Segoe UI,Arial,sans-serif;font-size:14px;font-weight:600;padding:11px 16px;border-radius:8px;">Download Payment Receipt</a>

                                        <hr style="border:none;border-top:1px solid #e5e7eb;margin:22px 0;"/>
                                        <p style="margin:0;font-family:Segoe UI,Arial,sans-serif;font-size:13px;line-height:1.6;color:#6b7280;">
                                            Best regards,<br/>
                                            <strong style="color:#1f2937;">Spheronix Hackathon Team</strong><br/>
                                            Bangalore, India
                                        </p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="background:#f8fafc;border-top:1px solid #e5e7eb;padding:12px 24px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#6b7280;">
                                        This is an automated transactional email regarding your Spheronix Hackathon registration.
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
    """

    return plain_body, html_body



def send_participant_confirmation_email(
    recipient_email: str,
    participant_name: str,
    role_text: str,
    participant_id: str,
    team_name: Optional[str],
    team_id: Optional[str],
    registration_doc: Dict[str, Any],
) -> None:
    mail_from = settings.mail_from or settings.smtp_user
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password or not mail_from:
        return

    payment = registration_doc.get("payment", {})
    amount = float(payment.get("amount") or 0)
    currency = payment.get("currency") or "INR"
    payment_status = str(payment.get("status") or "success").upper()
    transaction_id = payment.get("transaction_id") or "N/A"
    task_selected = str(registration_doc.get("task_selected") or registration_doc.get("project_selected") or "").strip()
    assigned_challenge = registration_doc.get("assigned_challenge") or {}

    paid_ts = payment.get("timestamp") or registration_doc.get("registeredAt") or utc_now()
    paid_date = format_datetime_ist(paid_ts)

    receipt_url = build_receipt_download_url(registration_doc.get("rzp_order_id", ""), recipient_email)
    plain_body, html_body = _build_email_bodies(
        participant_name=participant_name,
        role_text=role_text,
        participant_id=participant_id,
        team_name=team_name,
        team_id=team_id,
        task_selected=task_selected,
        assigned_challenge=assigned_challenge,
        transaction_id=transaction_id,
        amount=amount,
        currency=currency,
        payment_status=payment_status,
        paid_date=paid_date,
        receipt_url=receipt_url,
    )

    sender_name = "Spheronix Hackathon"
    from_address = mail_from
    envelope_from = mail_from

    smtp_domain = settings.smtp_user.split("@", 1)[1].strip().lower() if "@" in settings.smtp_user else ""
    from_domain = mail_from.split("@", 1)[1].strip().lower() if "@" in mail_from else ""

    if smtp_domain and from_domain and smtp_domain != from_domain:
        # Align visible sender with SMTP identity to improve DMARC/SPF alignment.
        from_address = settings.smtp_user
        envelope_from = settings.smtp_user
        logger.warning(
            "MAIL_FROM domain (%s) differs from SMTP_USER domain (%s). Using SMTP_USER for sender alignment.",
            from_domain,
            smtp_domain,
        )

    sender_domain = "localhost"
    if "@" in from_address:
        sender_domain = from_address.split("@", 1)[1].strip() or sender_domain

    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((sender_name, from_address))
    msg["To"] = recipient_email
    msg["Subject"] = "Spheronix Hackathon Registration Confirmed"
    msg["Date"] = formatdate(localtime=True)
    msg["Reply-To"] = from_address

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain_body, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    receipt_bytes = build_receipt_pdf(registration_doc, recipient_email)
    attachment = MIMEApplication(receipt_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename="Spheronix_Payment_Receipt.pdf")
    msg.attach(attachment)

    if settings.smtp_port == 465:
        # Fix P-05: Explicitly create default SSL context for certificate validation
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=25, context=ssl.create_default_context()) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(envelope_from, [recipient_email], msg.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=25) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(envelope_from, [recipient_email], msg.as_string())



async def send_confirmation_email_async(**kwargs: Any) -> None:
    await asyncio.to_thread(send_participant_confirmation_email, **kwargs)


async def _duplicate_exists(query: Dict[str, Any], rzp_order_id: str) -> bool:
    existing = await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "rzp_order_id": {"$ne": rzp_order_id},
            "$or": [query],
        },
        {"_id": 1},
    )
    return existing is not None


def _resolve_verified_payment_amount(
    expected_amount: float,
    payment_state: Dict[str, Any],
    submitted_amount: Optional[float],
) -> tuple[float, str]:
    if submitted_amount is not None:
        try:
            submitted_value = float(submitted_amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid payment amount submitted")
        if abs(submitted_value - expected_amount) > 0.01:
            raise HTTPException(status_code=400, detail=f"Invalid payment amount. Expected INR {expected_amount:.2f}")

    recorded_amount = payment_state.get("amount")
    if recorded_amount is None:
        final_amount = expected_amount
    else:
        try:
            final_amount = float(recorded_amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid recorded payment amount")

        if abs(final_amount - expected_amount) > 0.01:
            raise HTTPException(status_code=400, detail=f"Payment amount mismatch. Expected INR {expected_amount:.2f}")

    currency = str(payment_state.get("currency") or "INR")
    return final_amount, currency


def _resolve_selected_task(student: StudentRegister, existing_for_order: Dict[str, Any] | None) -> str:
    submitted_task = (student.projectSelected or "").strip()
    stored_task = ""
    if existing_for_order:
        stored_task = str(
            existing_for_order.get("task_selected") or existing_for_order.get("project_selected") or ""
        ).strip()

    if stored_task and submitted_task and stored_task != submitted_task:
        raise HTTPException(
            status_code=400,
            detail="Selected task does not match the payment order. Please restart the payment flow.",
        )

    resolved_task = stored_task or submitted_task
    if not resolved_task:
        raise HTTPException(status_code=400, detail="Task category is required for challenge assignment")
    return resolved_task


def _validate_no_local_duplicates(student: StudentRegister, member_dicts: List[Dict[str, Any]]) -> None:
    emails = {str(student.email).lower()}
    mobiles = {student.mobile}
    rolls = {student.rollNumber.lower()}

    for member in member_dicts:
        email = str(member["email"]).lower()
        mobile = member["mobile"]
        roll = member["rollNumber"].lower()

        if email in emails:
            raise HTTPException(status_code=400, detail="Duplicate email inside team members")
        if mobile in mobiles:
            raise HTTPException(status_code=400, detail="Duplicate mobile inside team members")
        if roll in rolls:
            raise HTTPException(status_code=400, detail="Duplicate roll number inside team members")

        emails.add(email)
        mobiles.add(mobile)
        rolls.add(roll)


async def _validate_global_duplicates(student: StudentRegister, member_dicts: List[Dict[str, Any]]) -> None:
    checks = [
        {"email": str(student.email)},
        {"leader.email": str(student.email)},
        {"team_members.email": str(student.email)},
        {"mobile": student.mobile},
        {"leader.phone": student.mobile},
        {"team_members.mobile": student.mobile},
        {"rollNumber": student.rollNumber},
        {"leader.rollNumber": student.rollNumber},
        {"team_members.rollNumber": student.rollNumber},
    ]

    for member in member_dicts:
        checks.extend(
            [
                {"team_members.email": str(member["email"])},
                {"team_members.mobile": member["mobile"]},
                {"team_members.rollNumber": member["rollNumber"]},
                {"email": str(member["email"])},
                {"leader.email": str(member["email"])},
                {"mobile": member["mobile"]},
                {"leader.phone": member["mobile"]},
                {"rollNumber": member["rollNumber"]},
                {"leader.rollNumber": member["rollNumber"]},
            ]
        )

    for query in checks:
        if await _duplicate_exists(query, student.rzp_order_id or ""):
            raise HTTPException(status_code=400, detail="Duplicate registration data detected.")


def _build_idempotent_response(existing_for_order: Dict[str, Any]) -> StudentResponse:
    participation_mode = str(existing_for_order.get("participationMode") or "individual").lower()
    leader = existing_for_order.get("leader") or {}
    team_members = existing_for_order.get("team_members") or []
    payment = existing_for_order.get("payment") or {}

    registration_id = str(existing_for_order.get("rzp_order_id") or "")
    participant_id = str(
        existing_for_order.get("participant_id")
        or leader.get("participant_id")
        or ""
    )
    participant_id = participant_id or None

    task_selected = str(
        existing_for_order.get("task_selected")
        or existing_for_order.get("project_selected")
        or ""
    ) or None
    transaction_id = str(payment.get("transaction_id") or "") or None
    payment_status = str(
        existing_for_order.get("payment_status")
        or payment.get("status")
        or "success"
    )

    if participation_mode == "team":
        team_member_ids = [
            str(member.get("participant_id"))
            for member in team_members
            if member.get("participant_id")
        ]
        team_member_emails = [
            str(member.get("email")).lower()
            for member in team_members
            if member.get("email")
        ]
        return StudentResponse(
            registrationId=registration_id,
            fullName=str(leader.get("name") or ""),
            email=str(leader.get("email") or "").lower(),
            participantId=participant_id,
            teamLeaderId=participant_id,
            teamMemberIds=team_member_ids,
            teamId=str(existing_for_order.get("team_id") or "") or None,
            transactionId=transaction_id,
            paymentStatus=payment_status,
            taskSelected=task_selected,
            assignedChallenge=None,  # Hide from user
            message="Team registration already completed for this payment order.",
            teamMemberEmails=team_member_emails,
            teamMemberNames=[member.get("name") for member in team_members if member.get("name")],
        )

    return StudentResponse(
        registrationId=registration_id,
        fullName=str(leader.get("name") or ""),
        email=str(leader.get("email") or "").lower(),
        participantId=participant_id,
        teamId=None,
        transactionId=transaction_id,
        paymentStatus=payment_status,
        taskSelected=task_selected,
        assignedChallenge=None,  # Hide from user
        message="Individual registration already completed for this payment order.",
    )


async def register_student(student: StudentRegister, rzp_payment_id: str | None, payment_status: str) -> StudentResponse:
    registration_time = ist_now()
    normalized_payment_status = (payment_status or "success").lower()
    if normalized_payment_status != "success":
        raise HTTPException(status_code=400, detail="Payment is not successful.")

    existing_for_order = await registrations_async_collection.find_one({"rzp_order_id": student.rzp_order_id})
    if existing_for_order and existing_for_order.get("registrationCompleted"):
        return _build_idempotent_response(existing_for_order)
    payment_state = existing_for_order.get("payment", {}) if existing_for_order else {}
    selected_task = _resolve_selected_task(student, existing_for_order)

    if student.participationMode == "team":
        member_models = student.teamMembers or []
        member_count = len(member_models)
        total_members = 1 + member_count

        if total_members < MIN_TEAM_TOTAL_MEMBERS:
            raise HTTPException(status_code=400, detail="Team must have at least 2 members including leader")
        if total_members > MAX_TEAM_TOTAL_MEMBERS:
            raise HTTPException(status_code=400, detail="Team cannot exceed 5 members including leader")
        if member_count > MAX_TEAM_MEMBERS_EXCLUDING_LEADER:
            raise HTTPException(status_code=400, detail="Maximum 4 team members allowed excluding leader")

        fee_per_member = await get_registration_fee()
        expected_amount = float(fee_per_member * total_members)
        paid_amount, paid_currency = _resolve_verified_payment_amount(
            expected_amount=expected_amount,
            payment_state=payment_state,
            submitted_amount=student.payment_amount,
        )

        team_name = (student.teamName or "").strip()
        if not team_name:
            raise HTTPException(status_code=400, detail="Team name is required for team registration")

        member_dicts = [member.model_dump() for member in member_models]
        _validate_no_local_duplicates(student, member_dicts)
        await _validate_global_duplicates(student, member_dicts)

        team_id = await generate_unique_team_id()
        leader_id = build_team_member_participant_id(team_id, 1)
        assigned_challenge = await assign_random_challenge(
            selected_task,
            team_id=team_id,
            registration_id=student.rzp_order_id,
        )

        enriched_members: List[Dict[str, Any]] = []
        for idx, member in enumerate(member_dicts, start=2):
            enriched_member = {
                "name": member["fullName"],
                "email": str(member["email"]).lower(),
                "mobile": member["mobile"],
                "rollNumber": member["rollNumber"],
                "githubProfile": member["githubProfile"],
                "branch": student.branch,
                "participant_id": build_team_member_participant_id(team_id, idx),
            }
            enriched_members.append(enriched_member)

        registration_doc: Dict[str, Any] = {
            "rzp_order_id": student.rzp_order_id,
            "registrationCompleted": True,
            "participationMode": "team",
            "team_id": team_id,
            "team_name": team_name,
            "project_selected": selected_task,
            "task_selected": assigned_challenge["title"],
            "assigned_challenge": assigned_challenge,
            "total_members": total_members,
            "payment_status": "success",
            "leader": {
                "participant_id": leader_id,
                "name": student.fullName,
            "email": str(student.email).lower(),
                "phone": student.mobile,
                "college": student.collegeName,
                "branch": student.branch,
                "city": student.city,
                "rollNumber": student.rollNumber,
                "githubProfile": student.githubProfile,
            },
            "team_members": enriched_members,
            "payment": {
                "transaction_id": rzp_payment_id,
                "order_id": student.rzp_order_id,
                "gateway": "razorpay",
                "amount": paid_amount,
                "currency": paid_currency,
                "status": "success",
                "timestamp": registration_time,
            },
            "updatedAt": registration_time,
        }
        
        insert_only_fields = {
            "createdAt": registration_time,
            "registeredAt": registration_time,
            "is_reviewed": False,
            "is_selected": False,
            "Reviewedby": None,
            "user_feedback": None,
            "password": "",
            "feedback": "",
            "github_link": "",
        }

        try:
            await registrations_async_collection.update_one(
                {"rzp_order_id": student.rzp_order_id},
                {
                    "$set": registration_doc,
                    "$setOnInsert": insert_only_fields,
                },
                upsert=True,
            )

            await teams_async_collection.update_one(
                {"teamId": team_id},
                {
                    "$set": {
                        "teamId": team_id,
                        "teamName": team_name,
                        "leaderEmail": str(student.email).lower(),
                        "leaderId": leader_id,
                        "collegeName": student.collegeName,
                        "branch": student.branch,
                        "projectSelected": selected_task,
                        "taskSelected": assigned_challenge["title"],
                        "assignedChallenge": assigned_challenge,
                        "paymentStatus": "success",
                        "payment": registration_doc["payment"],
                        "registrationId": student.rzp_order_id,
                        "members": [
                            {
                                "participant_id": leader_id,
                                "name": student.fullName,
                                "email": str(student.email).lower(),
                                "mobile": student.mobile,
                                "role": "leader",
                            }
                        ]
                        + [
                            {
                                "participant_id": member["participant_id"],
                                "name": member["name"],
                                "email": member["email"],
                                "mobile": member["mobile"],
                                "role": "member",
                            }
                            for member in enriched_members
                        ],
                        "totalMembers": total_members,
                        "updatedAt": registration_time,
                    },
                    "$setOnInsert": {"createdAt": registration_time},
                },
                upsert=True,
            )
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail="Duplicate registration conflict. Please retry.")

        await users_async_collection.update_one(
            {"email": str(student.email).lower()},
            {
                "$set": {"name": student.fullName, "googleId": None, "updatedAt": registration_time},
                "$setOnInsert": {"createdAt": registration_time},
            },
            upsert=True,
        )

        # Team leader + each member receive their own ID and receipt email individually.
        try:
            # Fix M-03: Send emails in the background to avoid blocking API response
            async def send_all_team_emails():
                try:
                    await asyncio.gather(
                        send_confirmation_email_async(
                            recipient_email=str(student.email).lower(),
                            participant_name=student.fullName,
                            role_text="team leader",
                            participant_id=leader_id,
                            team_name=team_name,
                            team_id=team_id,
                            registration_doc=registration_doc,
                        ),
                        *[
                            send_confirmation_email_async(
                                recipient_email=member["email"],
                                participant_name=member["name"],
                                role_text="team member",
                                participant_id=member["participant_id"],
                                team_name=team_name,
                                team_id=team_id,
                                registration_doc=registration_doc,
                            )
                            for member in enriched_members
                        ],
                    )
                except Exception as email_err:
                    logger.warning("Failed to send team confirmation emails: %s", email_err)
            
            asyncio.create_task(send_all_team_emails())
        except Exception as e:
            logger.warning("Failed to schedule team emails: %s", e)

        return StudentResponse(
            registrationId=student.rzp_order_id or "",
            fullName=student.fullName,
            email=str(student.email).lower(),
            participantId=leader_id,
            teamLeaderId=leader_id,
            teamMemberIds=[member["participant_id"] for member in enriched_members],
            teamId=team_id,
            transactionId=rzp_payment_id,
            paymentStatus="success",
            taskSelected=selected_task,
            assignedChallenge=None, # Hide from user
            message=(
                "Team registration successful. Team ID, challenge details, and receipts have been emailed to the leader and members."
            ),
            teamMemberEmails=[member["email"] for member in enriched_members],
            teamMemberNames=[member["name"] for member in enriched_members],
        )

    await _validate_global_duplicates(student, [])

    fee_per_member = await get_registration_fee()
    expected_amount = float(fee_per_member)
    paid_amount, paid_currency = _resolve_verified_payment_amount(
        expected_amount=expected_amount,
        payment_state=payment_state,
        submitted_amount=student.payment_amount,
    )

    individual_id = await generate_unique_individual_id()
    assigned_challenge = await assign_random_challenge(selected_task, registration_id=student.rzp_order_id)
    registration_doc = {
        "rzp_order_id": student.rzp_order_id,
        "registrationCompleted": True,
        "participationMode": "individual",
        "participant_id": individual_id,
        "team_id": None,
        "team_name": None,
        "project_selected": selected_task,
        "task_selected": assigned_challenge["title"],
        "assigned_challenge": assigned_challenge,
        "total_members": 1,
        "payment_status": "success",
        "leader": {
            "participant_id": individual_id,
            "name": student.fullName,
                "email": str(student.email).lower(),
            "phone": student.mobile,
            "college": student.collegeName,
            "branch": student.branch,
            "city": student.city,
            "rollNumber": student.rollNumber,
            "githubProfile": student.githubProfile,
        },
        "team_members": [],
        "payment": {
            "transaction_id": rzp_payment_id,
            "order_id": student.rzp_order_id,
            "gateway": "razorpay",
            "amount": paid_amount,
            "currency": paid_currency,
            "status": "success",
            "timestamp": registration_time,
        },
        "updatedAt": registration_time,
    }
    
    insert_only_fields = {
        "createdAt": registration_time,
        "registeredAt": registration_time,
        "is_reviewed": False,
        "is_selected": False,
        "Reviewedby": None,
        "user_feedback": None,
        "password": "",
        "feedback": "",
        "github_link": "",
    }

    try:
        await registrations_async_collection.update_one(
            {"rzp_order_id": student.rzp_order_id},
            {
                "$set": registration_doc,
                "$setOnInsert": insert_only_fields,
            },
            upsert=True,
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Duplicate registration conflict. Please retry.")

    await users_async_collection.update_one(
        {"email": str(student.email).lower()},
        {
            "$set": {"name": student.fullName, "googleId": None, "updatedAt": registration_time},
            "$setOnInsert": {"createdAt": registration_time},
        },
        upsert=True,
    )

    try:
        # Fix M-03: Send emails in the background to avoid blocking API response
        async def send_individual_email():
            try:
                await send_confirmation_email_async(
                    recipient_email=str(student.email).lower(),
                    participant_name=student.fullName,
                    role_text="individual",
                    participant_id=individual_id,
                    team_name=None,
                    team_id=None,
                    registration_doc=registration_doc,
                )
            except Exception as email_err:
                logger.warning("Failed to send individual confirmation email: %s", email_err)
        
        asyncio.create_task(send_individual_email())
    except Exception as e:
        logger.warning("Failed to schedule individual email: %s", e)

    return StudentResponse(
        registrationId=student.rzp_order_id or "",
        fullName=student.fullName,
        email=str(student.email).lower(),
        participantId=individual_id,
        teamId=None,
        transactionId=rzp_payment_id,
        paymentStatus="success",
        taskSelected=selected_task,
        assignedChallenge=None, # Hide from user
        message="Individual registration successful. Your registration details and receipt have been emailed.",
    )



