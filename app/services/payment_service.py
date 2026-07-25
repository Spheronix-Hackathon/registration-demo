import asyncio
import logging
import secrets
import hashlib
import razorpay

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.core.time_utils import ist_now, unix_timestamp, utc_now
from app.database.mongodb import registrations_async_collection
from app.models.schemas import PaymentOrderRequest, PaymentOrderResponse
from app.services.settings_service import get_registration_fee
from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
) if settings.razorpay_key_id and settings.razorpay_key_secret else None


async def verify_razorpay_payment(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> dict:
    if razorpay_signature == "mock_signature" and settings.app_env != "production":
        return {
            "razorpay_payment_id": razorpay_payment_id,
            "payment_status": "SUCCESS",
        }

    if not razorpay_client:
        raise HTTPException(status_code=500, detail="Razorpay is not configured")

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        return {
            "razorpay_payment_id": razorpay_payment_id,
            "payment_status": "SUCCESS",
        }
    except razorpay.errors.SignatureVerificationError as e:
        logger.error(f"Razorpay signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    except Exception as e:
        logger.error(f"Razorpay verification error: {e}")
        raise HTTPException(status_code=500, detail="Error verifying payment")


async def create_order(request: PaymentOrderRequest) -> PaymentOrderResponse:
    normalized_email = str(request.email).lower()
    selected_task = (request.projectSelected or '').strip()

    existing_registration = await registrations_async_collection.find_one(
        {
            "registrationCompleted": True,
            "$or": [
                {"email": normalized_email},
                {"leader.email": normalized_email},
                {"team_members.email": normalized_email},
            ],
        },
        {"_id": 1, "registrationCompleted": 1},
    )
    if existing_registration:
        raise HTTPException(status_code=409, detail="This email is already registered for the hackathon")

    base_amount = await get_registration_fee()
    if request.participationMode == "team":
        total_members = 1 + request.teamMembersCount
        amount = base_amount * total_members
    else:
        amount = base_amount

    # amount in paise for razorpay
    razorpay_amount = int(amount * 100)
    receipt_id = f"rcpt_{unix_timestamp()}_{secrets.token_hex(4)}"

    total_members = 1 + request.teamMembersCount if request.participationMode == "team" else 1
    update_filter = {"email": normalized_email}
    if existing_registration and existing_registration.get("_id") is not None:
        update_filter = {"_id": existing_registration["_id"]}

    # Prevent resetting a successful payment status if the user already paid but refreshed.
    existing_doc = await registrations_async_collection.find_one(update_filter, {"payment": 1, "rzp_order_id": 1})
    is_already_paid = existing_doc and str(existing_doc.get("payment", {}).get("status") or "").lower() in ["success", "paid", "captured"]
    
    # Fix H-01: Determine environment from key prefix instead of hardcoding "PRODUCTION"
    razorpay_env = "PRODUCTION" if settings.razorpay_key_id.startswith("rzp_live_") else "TEST"

    if is_already_paid:
        return PaymentOrderResponse(
            orderId=existing_doc.get("rzp_order_id") or "already_paid",
            amount=float(amount),
            currency="INR",
            paymentSessionId="",
            paymentGateway="razorpay",
            environment=razorpay_env,
            razorpayKeyId=settings.razorpay_key_id,
            mockMode=True,
            mockPaymentId=existing_doc.get("payment", {}).get("transaction_id") or "already_paid",
            message="Payment already completed"
        )

    update_data = {
        "registrationCompleted": False,
        "email": normalized_email,
        "fullName": request.fullName,
        "participationMode": request.participationMode,
        "mobile": request.mobile,
        "totalMembers": total_members,
        "project_selected": selected_task or None,
        "task_selected": None,
        "updatedAt": ist_now(),
        "registeredAt": None,
        "is_reviewed": False,
        "is_selected": False,
        "Reviewedby": None,
        "user_feedback": None,
        "password": "",
        "feedback": "",
        "github_link": "",
    }

    try:
        if not razorpay_client:
            raise Exception("Razorpay client is not configured")

        order = None
        last_exception = None
        for attempt in range(3):
            try:
                order = razorpay_client.order.create({
                    "amount": razorpay_amount,
                    "currency": "INR",
                    "receipt": receipt_id,
                    "notes": {
                        "email": normalized_email,
                        "name": request.fullName
                    }
                })
                break
            except Exception as e:
                last_exception = e
                logger.warning(f"Razorpay order creation attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        
        if not order:
            raise Exception(f"Failed to create Razorpay order after 3 attempts. Last error: {last_exception}")


        rzp_order_id = order["id"]
        update_data["rzp_order_id"] = rzp_order_id

        update_data["payment"] = {
            "gateway": "razorpay",
            "status": "created",
            "transaction_id": None,
            "amount": float(amount),
            "currency": "INR",
            "timestamp": ist_now(),
        }

        await registrations_async_collection.update_one(
            update_filter,
            {
                "$set": update_data,
                "$setOnInsert": {
                    "createdAt": ist_now(),
                },
            },
            upsert=True,
        )

        return PaymentOrderResponse(
            orderId=rzp_order_id,
            amount=float(amount),
            currency="INR",
            paymentSessionId="",  # Not used in Razorpay basic flow
            paymentGateway="razorpay",
            environment=razorpay_env,
            razorpayKeyId=settings.razorpay_key_id,
            mockMode=False,
            mockPaymentId=None,
            message="Order created successfully"
        )
    except DuplicateKeyError as exc:
        logger.exception("Mongo duplicate key error while creating payment order")
        if "participantId_1" in str(exc) or "participant_id_1" in str(exc):
            raise HTTPException(
                status_code=500,
                detail=(
                    "Database index conflict on participant_id. "
                    "This usually happens if older uniqueness constraints are still active. "
                    "Please restart the server to run the database cleanup scripts."
                ),
            )
        raise HTTPException(status_code=409, detail="A unique constraint error occurred. Please try again.")
    except Exception as exc:
        is_missing_keys = str(exc) == "Razorpay client is not configured"
        
        if not is_missing_keys:
            logger.error(f"Razorpay order creation completely failed: {exc}")
            raise HTTPException(
                status_code=500, 
                detail="Payment gateway is temporarily unavailable. Please try again later."
            )
            
        logger.warning("Razorpay client not configured. Falling back to mock mode.")
        if settings.app_env != "production" or is_missing_keys:
            mock_order_id = f"MOCK_RZP_{unix_timestamp()}_{secrets.token_hex(3)}"
            mock_payment_id = f"MOCK_PAY_{secrets.token_hex(6)}"

            update_data["rzp_order_id"] = mock_order_id
            if not is_already_paid:
                update_data["payment"] = {
                    "gateway": "razorpay",
                    "status": "created",
                    "transaction_id": mock_payment_id,
                    "amount": float(amount),
                    "currency": "INR",
                    "mock_mode": True,
                    "timestamp": ist_now(),
                }

            await registrations_async_collection.update_one(
                update_filter,
                {
                    "$set": update_data,
                    "$setOnInsert": {
                        "createdAt": ist_now(),
                    },
                },
                upsert=True,
            )

            return PaymentOrderResponse(
                orderId=mock_order_id,
                amount=float(amount),
                currency="INR",
                paymentSessionId="MOCK_SESSION",
                paymentGateway="razorpay",
                environment="SANDBOX",
                razorpayKeyId="mock_key_id",
                mockMode=True,
                mockPaymentId=mock_payment_id,
                message="Razorpay request failed or missing credentials. Mock payment mode enabled for local testing.",
            )

        logger.exception("Unexpected error in create_order")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing the payment order.")
