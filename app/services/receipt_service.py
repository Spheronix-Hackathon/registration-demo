import io
from datetime import datetime
from typing import Any, Dict
from urllib.parse import quote

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor

from app.core.time_utils import ensure_ist, format_ist, utc_now
from config.settings import get_settings

settings = get_settings()
# Fix H-07: Use URLSafeTimedSerializer so receipt links expire after 30 days
serializer = URLSafeTimedSerializer(settings.secret_key, salt="receipt-download")
RECEIPT_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


def format_datetime_ist(value: Any) -> str:
    if isinstance(value, datetime):
        return ensure_ist(value).strftime("%Y-%m-%d %H:%M:%S IST")
    return str(value)


def create_receipt_token(registration_id: str, email: str) -> str:
    # URLSafeTimedSerializer.dumps() automatically embeds a timestamp
    return serializer.dumps({"registration_id": registration_id, "email": email.lower()})


def verify_receipt_token(token: str, registration_id: str, email: str) -> bool:
    try:
        # Fix H-07: Enforce token expiry (30 days)
        payload = serializer.loads(token, max_age=RECEIPT_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return False

    return (
        payload.get("registration_id") == registration_id
        and payload.get("email") == email.lower()
    )


def build_receipt_download_url(registration_id: str, email: str) -> str:
    token = create_receipt_token(registration_id, email)
    # Defensively clean the base URL: strip comments, whitespace, trailing slashes,
    # and take only the first entry if a comma-separated list was accidentally configured.
    raw_base = settings.app_base_url or "http://127.0.0.1:8000"
    raw_base = raw_base.split("#")[0].strip()           # remove inline comments
    raw_base = raw_base.split(",")[0].strip()           # take only first URL if list
    base = raw_base.rstrip("/")
    safe_email = quote(email)
    safe_token = quote(token)
    return f"{base}/api/receipt/{registration_id}?email={safe_email}&token={safe_token}"


def build_receipt_pdf(registration_doc: Dict[str, Any], requested_email: str) -> bytes:
    """
    Generates a PDF receipt using ReportLab for Unicode support.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Colors
    primary_color = HexColor("#007AFF")
    text_dark = HexColor("#1A202C")
    text_gray = HexColor("#4A5568")

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(primary_color)
    c.drawString(55, height - 80, "Spheronix Hackathon 2026")

    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(text_dark)
    c.drawString(55, height - 120, "Payment Receipt")

    payment_data = registration_doc.get("payment", {})
    tz_aware_ts = ensure_ist(payment_data.get("timestamp") or utc_now())
    date_str = format_ist(tz_aware_ts)

    c.setFont("Helvetica", 10)
    c.setFillColor(text_gray)
    c.drawString(55, height - 145, f"Date: {date_str}")
    c.drawString(55, height - 160, f"Order ID: {registration_doc.get('rzp_order_id', 'N/A')}")
    c.drawString(55, height - 175, f"Transaction ID: {payment_data.get('transaction_id', 'N/A')}")

    # Separator Line
    c.setStrokeColor(HexColor("#E2E8F0"))
    c.line(55, height - 200, width - 55, height - 200)

    # Participant Details (Find the relevant person based on requested_email)
    leader = registration_doc.get("leader", {})
    members = registration_doc.get("team_members", [])

    is_leader = str(leader.get("email", "")).lower() == requested_email.lower()
    target_person = leader if is_leader else next(
        (m for m in members if str(m.get("email", "")).lower() == requested_email.lower()), {}
    )

    details = [
        ("Name", target_person.get("name", "N/A")),
        ("Email", target_person.get("email", "N/A")),
        ("Participant ID", target_person.get("participant_id", "N/A")),
        ("Role", "Team Leader" if is_leader else ("Team Member" if members else "Individual")),
        ("Participation Mode", registration_doc.get("participationMode", "individual").title()),
    ]

    if registration_doc.get("team_name"):
        details.append(("Team Name", registration_doc.get("team_name", "")))

    details.append(("Total Amount", f"INR {payment_data.get('amount', 0.0)}"))
    details.append(("Payment Status", str(payment_data.get('status', 'N/A')).upper()))

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(text_dark)
    c.drawString(55, height - 240, "Participant Details")

    y = height - 270
    for label, value in details:
        safe_label = str(label)
        safe_value = str(value)

        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(text_dark)
        c.drawString(55, y, f"{safe_label}:")

        c.setFont("Helvetica", 10)
        c.setFillColor(text_gray)
        c.drawString(180, y, safe_value)
        y -= 20

    # Footer
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#4A5568"))
    c.drawString(55, 100, "This is a system-generated receipt and serves as official proof of payment.")
    
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(text_dark)
    c.drawString(55, 80, "Spheronix Hackathon Team")

    c.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
