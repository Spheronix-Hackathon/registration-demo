from __future__ import annotations

import logging

from app.core.time_utils import format_ist


class ISTFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return format_ist(fmt=datefmt or "%Y-%m-%d %H:%M:%S IST")


def configure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    formatter = ISTFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)

    root_logger.setLevel(level)