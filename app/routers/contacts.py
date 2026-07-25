import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field

from app.core.rate_limit import limiter

from app.database.mongodb import contacts_async_collection
from app.services.contact_service import send_contact_acknowledgement
from app.core.time_utils import ist_timestamp

router = APIRouter(prefix="/api/contacts", tags=["contacts"])
logger = logging.getLogger(__name__)


class ContactMessage(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # Fix M-02: Removed Gmail-only restriction — accept any valid email address
    email: EmailStr
    mobile: str = Field(..., pattern=r"^\d{10}$")
    message: str = Field(..., min_length=1, max_length=2000)


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def create_contact_message(request: Request, contact: ContactMessage, background_tasks: BackgroundTasks):
    try:
        document = contact.model_dump()
        document["email"] = document["email"].lower()
        document["timestamp"] = ist_timestamp()

        result = await contacts_async_collection.insert_one(document)

        if result.inserted_id:
            logger.info(f"Contact message from {contact.email} saved successfully")

            # Send acknowledgment email in background (non-blocking)
            background_tasks.add_task(send_contact_acknowledgement, contact.email, contact.name)

            return {"message": "Message saved successfully", "id": str(result.inserted_id)}

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save message"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error saving contact message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
