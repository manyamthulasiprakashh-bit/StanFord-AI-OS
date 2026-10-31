"""Centralized, privacy-safe logging configuration for Stanford-AI OS."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from .context import get_request_id

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

ALLOWED_LOG_FIELDS = frozenset(
    {
        "task_id",
        "execution_id",
        "provider",
        "model",
        "duration_ms",
        "outcome",
        "error_category",
        "status_code",
    }
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", None) or record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if payload["request_id"] is None:
            payload["request_id"] = get_request_id()

        for field in ALLOWED_LOG_FIELDS:
            if hasattr(record, field):
                payload[field] = _json_safe(getattr(record, field))

        return json.dumps(payload, default=str)


def configure_logging(level: str | None = None) -> None:
    """Configure the application logger without duplicating handlers."""

    if level is None:
        level = os.getenv("STANFORD_AI_OS_LOG_LEVEL", "INFO")

    level_name = str(level).upper()
    if level_name not in VALID_LOG_LEVELS:
        level_name = "INFO"

    numeric_level = getattr(logging, level_name)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    handler = None
    for existing in root_logger.handlers:
        if getattr(existing, "_stanford_ai_os", False):
            handler = existing
            break

    if handler is None:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._stanford_ai_os = True
        root_logger.addHandler(handler)

    handler.setLevel(numeric_level)
    for existing in root_logger.handlers:
        if getattr(existing, "_stanford_ai_os", False):
            existing.setLevel(numeric_level)


def log_event(
    logger: logging.Logger, level: int, event: str, **fields: Any
) -> None:
    """Emit a structured, allowlisted log event."""

    safe_fields = {}
    for key, value in fields.items():
        if key in ALLOWED_LOG_FIELDS:
            safe_fields[key] = _json_safe(value)

    extra = {"event": event, "request_id": get_request_id()}
    extra.update(safe_fields)
    logger.log(level, event, extra=extra)
