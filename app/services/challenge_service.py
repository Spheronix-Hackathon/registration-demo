import random
from typing import Any

from fastapi import HTTPException

from app.core.time_utils import utc_now
from app.database.mongodb import (
    hackathon_challenges_async_collection,
    registrations_async_collection,
    teams_async_collection,
)


def serialize_assigned_challenge(document: dict[str, Any] | None) -> dict[str, str] | None:
    if not document:
        return None

    title = str(document.get("title") or "").strip()
    description = str(document.get("description") or "").strip()
    if not title or not description:
        return None

    return {
        "category": str(document.get("category") or "").strip(),
        "title": title,
        "description": description,
    }


async def assign_random_challenge(
    task_category: str,
    team_id: str | None = None,
    registration_id: str | None = None,
) -> dict[str, str]:
    normalized_category = (task_category or "").strip()
    if not normalized_category:
        raise HTTPException(status_code=400, detail="Task category is required for challenge assignment")

    # 1. Fetch available questions for this category from global data
    from app.database.mongodb import global_data_async_collection
    global_doc = await global_data_async_collection.find_one({"name": normalized_category})
    if not global_doc or not global_doc.get("questions"):
        # Fallback to category name if no questions found in global data,
        # but the user expects it to be from global data.
        raise HTTPException(
            status_code=500,
            detail=f"No questions configured for category '{normalized_category}' in global data",
        )

    available_questions = global_doc["questions"]
    selected_question = random.choice(available_questions)

    if isinstance(selected_question, dict):
        selected_challenge = {
            "category": normalized_category,
            "title": selected_question.get("name", ""),
            "description": selected_question.get("description", ""),
            "requirements": selected_question.get("requirements", ""),
            "projectUrl": selected_question.get("projectUrl", "")
        }
    else:
        # Legacy support for older string-based questions
        selected_challenge = {
            "category": normalized_category,
            "title": str(selected_question),
            "description": "Challenge details not provided."
        }

    if not selected_challenge or not selected_challenge.get("title"):
        raise HTTPException(status_code=500, detail="Selected hackathon challenge is invalid")

    if team_id:
        await teams_async_collection.update_one(
            {"teamId": team_id},
            {
                "$set": {
                    "assignedChallenge": selected_challenge,
                    "updatedAt": utc_now(),
                }
            },
        )

    if registration_id:
        await registrations_async_collection.update_one(
            {"rzp_order_id": registration_id},
            {
                "$set": {
                    "assigned_challenge": selected_challenge,
                    "updatedAt": utc_now(),
                }
            },
        )

    return selected_challenge


async def get_registration_summary(registration_id: str) -> dict[str, Any]:
    registration = await registrations_async_collection.find_one({"rzp_order_id": registration_id}, {"_id": 0})
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    payment = registration.get("payment", {})
    payment_status = str(payment.get("status") or "").lower()

    # Allow summary only if registration is completed
    if not registration.get("registrationCompleted"):
        raise HTTPException(status_code=404, detail="Registration not yet finalized")

    leader = registration.get("leader", {})
    team_members = registration.get("team_members", [])

    return {
        "registrationId": str(registration.get("rzp_order_id") or ""),
        "transactionId": payment.get("transaction_id"),
        "fullName": str(leader.get("name") or registration.get("fullName") or ""),
        "email": str(leader.get("email") or registration.get("email") or "").lower(),
        "participantId": leader.get("participant_id") or registration.get("participant_id"),
        "teamId": registration.get("team_id"),
        "teamName": registration.get("team_name"),
        "taskSelected": registration.get("project_selected") or registration.get("task_selected"),
        "assignedChallenge": None, # Hide from user
        "paymentStatus": payment.get("status"),
        "teamMemberEmails": [
            str(member.get("email") or "").lower()
            for member in team_members
            if member.get("email")
        ],
        "is_reviewed": bool(registration.get("is_reviewed", False)),
        "is_selected": bool(registration.get("is_selected", False)),
        # Fix L-01: Renamed from Reviewedby to reviewed_by for consistent snake_case
        "reviewed_by": registration.get("Reviewedby"),
        "user_feedback": registration.get("user_feedback"),
    }