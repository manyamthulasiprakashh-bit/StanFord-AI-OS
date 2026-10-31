"""Request-scoped context helpers for Stanford-AI OS."""

from __future__ import annotations

import contextvars
import uuid

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> str | None:
    """Return the request ID for the current context, if any."""

    return request_id_var.get()


def set_request_id(value: str | None = None) -> contextvars.Token:
    """Set and return a token for the current request ID."""

    if value is None:
        value = str(uuid.uuid4())
    return request_id_var.set(value)


def reset_request_id(token: contextvars.Token) -> None:
    """Reset the request ID context to its previous state."""

    request_id_var.reset(token)
