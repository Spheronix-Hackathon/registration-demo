import asyncio
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

def _send_email_sync(recipient_email: str, name: str):
    mail_from = settings.mail_from or settings.smtp_user
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password, mail_from]):
        logger.warning("SMTP settings not fully configured. Email acknowledgement skipped.")
        return

    subject = "Message Received - Spheronix Hackathon 2026"
    
    plain_body = f"""Hello {name},

Thank you for reaching out to us! 

We have received your message through the Spheronix Hackathon 2026 contact form. Our team is currently reviewing your inquiry and will get back to you shortly at this email address.

Regards,
Spheronix Hackathon Team
This is an automated acknowledgment message.
"""

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e1e1e1; border-radius: 10px;">
                <h2 style="color: #0284c7;">Message Received!</h2>
                <p>Hello <strong>{name}</strong>,</p>
                <p>Thank you for reaching out to us! We have received your message regarding the Spheronix Hackathon 2026.</p>
                <p>Our team is currently reviewing your inquiry and will get back to you shortly at this email address.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 0.9em; color: #666;">
                    Regards,<br>
                    <strong>Spheronix Hackathon Team</strong>
                </p>
                <p style="font-size: 0.8em; color: #999; margin-top: 15px;">
                    This is an automated acknowledgment message. Please do not reply directly to this email.
                </p>
            </div>
        </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Spheronix Hackathon Team", mail_from))
    msg["To"] = recipient_email
    msg["Date"] = formatdate(localtime=True)

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.smtp_port == 465:
            # Fix P-05: Explicitly create default SSL context for certificate validation
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=ssl.create_default_context()) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(mail_from, [recipient_email], msg.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(mail_from, [recipient_email], msg.as_string())
        logger.info(f"Acknowledgement email sent to {recipient_email}")
    except Exception as e:
        logger.error(f"Failed to send acknowledgement email to {recipient_email}: {str(e)}")

async def send_contact_acknowledgement(email: str, name: str):
    # Run sync SMTP operation in a thread to keep FastAPI async
    await asyncio.to_thread(_send_email_sync, email, name)
