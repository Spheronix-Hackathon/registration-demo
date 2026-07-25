import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.rate_limit import limiter
from app.core.time_utils import utc_now
from app.database.mongodb import registrations_async_collection
from app.models.schemas import PaymentOrderRequest, PaymentVerification
from app.services.payment_service import create_order, verify_razorpay_payment, razorpay_client
from config.settings import get_settings

router = APIRouter(prefix="/api/payment", tags=["payments"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/order")
@limiter.limit("5/minute")
async def create_payment_order(request: Request, payload: PaymentOrderRequest):
    return await create_order(payload)


@router.post("/verify")
@limiter.limit("5/minute")
async def verify_payment(request: Request, data: PaymentVerification):
    try:
        # Check if already paid to support recovery/mock modes
        existing_doc = await registrations_async_collection.find_one(
            {"rzp_order_id": data.razorpay_order_id}, 
            {"payment.status": 1, "payment.transaction_id": 1}
        )
        if existing_doc and str(existing_doc.get("payment", {}).get("status") or "").lower() in ["success", "paid", "captured"]:
            rzp_payment_id = existing_doc.get("payment", {}).get("transaction_id") or data.razorpay_payment_id
        else:
            verified_payment = await verify_razorpay_payment(
                data.razorpay_order_id, data.razorpay_payment_id, data.razorpay_signature
            )
            rzp_payment_id = verified_payment.get("razorpay_payment_id")

        payment_status = "success"

        # Fix B-03: Use update_one WITHOUT upsert=True to avoid phantom documents
        await registrations_async_collection.update_one(
            {"rzp_order_id": data.razorpay_order_id},
            {
                "$set": {
                    "payment": {
                        "gateway": "razorpay",
                        "transaction_id": rzp_payment_id,
                        "status": payment_status,
                        "timestamp": utc_now(),
                    },
                    "verifiedAt": utc_now(),
                    "updatedAt": utc_now(),
                    "password": "",
                    "feedback": "",
                    "github_link": "",
                },
            },
            # Removed upsert=True intentionally: payment must be created via /order first
        )

        return {
            "status": "success",
            "message": "Payment verified successfully",
            "rzp_order_id": data.razorpay_order_id,
            "rzp_payment_id": rzp_payment_id,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Payment verification error: {exc}")


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None, alias="X-Razorpay-Signature"),
):
    raw_body = await request.body()

    # Fix C-02: Verify webhook signature before processing
    if settings.razorpay_webhook_secret:
        if not x_razorpay_signature:
            logger.warning("Razorpay webhook received without signature header — rejecting")
            raise HTTPException(status_code=400, detail="Missing webhook signature")
        try:
            if razorpay_client:
                razorpay_client.utility.verify_webhook_signature(
                    raw_body.decode("utf-8"),
                    x_razorpay_signature,
                    settings.razorpay_webhook_secret,
                )
        except Exception:
            logger.warning("Razorpay webhook signature verification failed — rejecting")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
    else:
        # Webhook secret not configured — log a warning but allow (graceful degradation).
        # Set RAZORPAY_WEBHOOK_SECRET in your Razorpay Dashboard → Webhooks to enable verification.
        logger.warning(
            "RAZORPAY_WEBHOOK_SECRET is not configured. "
            "Webhook signature verification is DISABLED. Set it immediately for production security."
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event")

    if event not in ["payment.captured", "payment.failed", "payment.authorized"]:
        return {"status": "ignored", "message": "Unhandled event type"}

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    rzp_order_id = payment_entity.get("order_id")
    rzp_payment_id = payment_entity.get("id")
    payment_status = payment_entity.get("status")

    if not rzp_order_id:
        return {"status": "ignored", "message": "Webhook does not contain order ID"}

    # Fix B-03: Remove upsert=True — only update existing orders, never create phantom docs
    result = await registrations_async_collection.update_one(
        {"rzp_order_id": rzp_order_id},
        {
            "$set": {
                "payment": {
                    "gateway": "razorpay",
                    "transaction_id": rzp_payment_id,
                    "status": payment_status,
                    "timestamp": utc_now(),
                },
                "webhookPayload": payload,
                "updatedAt": utc_now(),
            },
        },
        # No upsert — we don't create docs from webhooks for unknown order IDs
    )

    if result.matched_count == 0:
        logger.warning(
            "Razorpay webhook for order_id=%s did not match any registration document. "
            "Possible replay attack or test webhook.",
            rzp_order_id,
        )
        return {"status": "ignored", "message": "Order not found"}

    return {"status": "success"}
