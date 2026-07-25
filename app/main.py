import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler

from app.core.logging_utils import configure_logging
from app.core.time_utils import ist_timestamp
from app.core.rate_limit import limiter
from app.database.mongodb import async_client, initialize_async_collections
from app.routers import auth, colleges, payments, students, teams, tasks, contacts, exports, settings as public_settings
from config.settings import get_settings

settings = get_settings()

configure_logging(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await initialize_async_collections()
    yield


# Fix M-04: Disable /docs and /redoc in production
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Fix H-02: Register SlowAPI rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.is_production,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Fix H-07: Only trust 127.0.0.1 (Nginx) as reverse proxy, not all hosts
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "::1"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logging.getLogger("app").exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "timestamp": ist_timestamp(),
        },
    )


@app.get("/")
async def read_root():
    return RedirectResponse(url="/new_landing.html")


# Fix P-02: Health check now pings MongoDB to report real connectivity
@app.get("/api/health")
async def health_check():
    db_status = "disconnected"
    try:
        await async_client.admin.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    overall = "running" if db_status == "connected" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "timestamp": ist_timestamp(),
        "environment": settings.app_env,
        "timezone": "Asia/Kolkata",
    }


app.include_router(auth.router)
app.include_router(colleges.router)
app.include_router(payments.router)
app.include_router(students.router)
app.include_router(teams.router)
app.include_router(tasks.router)
app.include_router(contacts.router)
app.include_router(exports.router)
app.include_router(public_settings.router)

# Serve static files at root
static_app = StaticFiles(directory="static", html=True)

async def static_handler(scope, receive, send):
    if scope["type"] != "http":
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1000})
        return
    await static_app(scope, receive, send)

app.mount("/", static_handler, name="static")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.server_host, port=settings.server_port, reload=False)
