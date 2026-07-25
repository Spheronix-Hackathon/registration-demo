from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


try:
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = UTC


def utc_now() -> datetime:
    return datetime.now(UTC)


def ist_now() -> datetime:
    return utc_now().astimezone(IST)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def ensure_ist(value: datetime) -> datetime:
    return ensure_utc(value).astimezone(IST)


def ist_timestamp(value: datetime | None = None) -> str:
    current = ensure_ist(value or utc_now())
    return current.isoformat(timespec="seconds")


def format_ist(value: datetime | None = None, fmt: str = "%Y-%m-%d %H:%M:%S IST") -> str:
    current = ensure_ist(value or utc_now())
    return current.strftime(fmt)


def unix_timestamp(value: datetime | None = None) -> int:
    current = ensure_utc(value or utc_now())
    return int(current.timestamp())