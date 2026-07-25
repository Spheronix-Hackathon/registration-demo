from urllib.parse import urlparse

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.core.rate_limit import limiter

from app.core.time_utils import ist_now
from app.database.mongodb import registrations_async_collection, users_async_collection
from config.settings import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])


def safe_js_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
@limiter.limit("10/minute")
async def login_via_google(request: Request):
    req_url_str = str(request.base_url).rstrip("/")
    if settings.app_base_url and "localhost" not in req_url_str and "127.0.0.1" not in req_url_str:
        base = settings.app_base_url.rstrip("/")
    else:
        base = req_url_str

    redirect_path = request.app.url_path_for("auth_callback")
    request_based_redirect = f"{base}{redirect_path}"

    # Keep host consistent between /login and /callback so OAuth state in session cookie matches.
    if settings.google_redirect_uri:
        configured = settings.google_redirect_uri.strip()
        try:
            configured_host = (urlparse(configured).hostname or "").lower()
            request_host = (request.url.hostname or "").lower()
            redirect_uri = configured if configured_host == request_host else request_based_redirect
        except Exception:
            redirect_uri = request_based_redirect
    else:
        redirect_uri = request_based_redirect

    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
@limiter.limit("10/minute")
async def auth_callback(request: Request):
    # Fix C-04: Use specific origin instead of wildcard "*" in postMessage
    target_origin = str(request.base_url).rstrip("/")
    if settings.app_base_url and "localhost" not in target_origin and "127.0.0.1" not in target_origin:
        target_origin = settings.app_base_url.rstrip("/")

    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")
        if not user_info:
            user_info = await oauth.google.userinfo(token=token)

        email = str(user_info.get("email") or "").strip().lower()
        name = user_info.get("name", "")
        google_id = user_info.get("sub")

        if not email:
            raise HTTPException(status_code=400, detail="Google account email not available")

        await users_async_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "email": email,
                    "name": name,
                    "googleId": google_id,
                    "lastLoginAt": ist_now(),
                },
                "$setOnInsert": {"createdAt": ist_now()},
            },
            upsert=True,
        )

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
        already_registered = existing is not None

        # Fix C-04: Use target_origin instead of "*" in postMessage
        html_content = f"""
            <!DOCTYPE html>
            <html><head><title>Authenticating...</title></head><body>
            <script>
                try {{
                    window.opener.postMessage({{
                        "status": "success",
                        "email": "{safe_js_text(email)}",
                        "name": "{safe_js_text(name)}",
                        "google_id": "{safe_js_text(google_id or '')}",
                        "alreadyRegistered": {"true" if already_registered else "false"}
                    }}, "{safe_js_text(target_origin)}");
                }} catch(e) {{}}
                window.close();
            </script>
            </body></html>
        """
        response = HTMLResponse(html_content)
        response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
        return response
    except Exception as exc:
        error_text = str(exc)
        if "mismatching_state" in error_text.lower():
            error_text = (
                "Session state mismatch. Open the site using only one host (either localhost or 127.0.0.1), "
                "clear browser cookies for this app, and retry Google login."
            )
        # Fix C-04: Use target_origin instead of "*" for the error postMessage too
        html_error = f"""
            <!DOCTYPE html>
            <html><head><title>Auth Error</title></head><body>
            <script>
                try {{
                    window.opener.postMessage({{
                        "status": "failed",
                        "error": "{safe_js_text(error_text)}"
                    }}, "{safe_js_text(target_origin)}");
                }} catch(e) {{}}
                window.close();
            </script>
            </body></html>
        """
        response = HTMLResponse(html_error)
        response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
        return response
