"""Authentication and authorization helpers."""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from stanford_ai_os.config import Settings, get_settings
from stanford_ai_os.db.models import User
from stanford_ai_os.db.session import get_db
from stanford_ai_os.observability.logging_config import log_event
from stanford_ai_os.schemas.auth import UserRead

password_hasher = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

logger = logging.getLogger(__name__)


class RateLimiter:
    """A small in-memory rate limiter for login attempts."""

    def __init__(self) -> None:
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(
        self,
        key: str,
        *,
        now: float | None = None,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
    ) -> bool:
        settings = get_settings()
        if max_attempts is None:
            max_attempts = settings.login_rate_limit_attempts
        if window_seconds is None:
            window_seconds = settings.login_rate_limit_window_seconds

        current_time = time.monotonic() if now is None else now
        cutoff = current_time - window_seconds

        with self._lock:
            attempts = self._attempts.setdefault(key, [])
            attempts[:] = [timestamp for timestamp in attempts if timestamp > cutoff]
            if len(attempts) >= max_attempts:
                return False
            attempts.append(current_time)
            return True

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


LoginRateLimiter = RateLimiter
ExecutionRateLimiter = RateLimiter


login_rate_limiter = LoginRateLimiter()
execution_rate_limiter = ExecutionRateLimiter()


def check_login_rate_limit(
    key: str,
    *,
    now: float | None = None,
    max_attempts: int | None = None,
    window_seconds: int | None = None,
) -> bool:
    """Return whether a login attempt is allowed."""

    settings = get_settings()
    if max_attempts is None:
        max_attempts = settings.login_rate_limit_attempts
    if window_seconds is None:
        window_seconds = settings.login_rate_limit_window_seconds

    return login_rate_limiter.is_allowed(
        key,
        now=now,
        max_attempts=max_attempts,
        window_seconds=window_seconds,
    )


def reset_login_rate_limits() -> None:
    """Clear in-memory login rate-limit state."""

    login_rate_limiter.reset()


def check_execution_rate_limit(
    key: str,
    *,
    now: float | None = None,
    max_attempts: int | None = None,
    window_seconds: int | None = None,
) -> bool:
    """Return whether an execution request is allowed."""

    settings = get_settings()
    if max_attempts is None:
        max_attempts = settings.execution_rate_limit_attempts
    if window_seconds is None:
        window_seconds = settings.execution_rate_limit_window_seconds

    return execution_rate_limiter.is_allowed(
        key,
        now=now,
        max_attempts=max_attempts,
        window_seconds=window_seconds,
    )


def reset_execution_rate_limits() -> None:
    """Clear in-memory execution rate-limit state."""

    execution_rate_limiter.reset()



class AuthenticationConfigurationError(Exception):
    """Raised when authentication is not configured correctly."""


class AuthenticationError(Exception):
    """Raised when authentication fails."""


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def _require_secret_key() -> str:
    secret_key = get_settings().secret_key
    if not secret_key or len(secret_key) < 32:
        raise AuthenticationConfigurationError("Authentication is not configured")
    return secret_key


def create_access_token(
    subject: str,
    secret_key: str | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    resolved_secret_key = secret_key if secret_key is not None else _require_secret_key()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, resolved_secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str | None = None) -> str:
    resolved_secret_key = secret_key if secret_key is not None else _require_secret_key()
    try:
        payload = jwt.decode(token, resolved_secret_key, algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired token") from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthenticationError("Invalid or expired token")
    return subject


def bootstrap_admin_user(db: Session, settings: Settings | None = None) -> User | None:
    if settings is None:
        settings = get_settings()
    if not settings.admin_password:
        return None

    try:
        _require_secret_key()
    except AuthenticationConfigurationError:
        return None

    existing_user = db.query(User).filter(User.username == settings.admin_username).first()
    if existing_user is not None:
        return existing_user

    user = User(
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        subject = decode_access_token(token)
    except AuthenticationError as exc:
        log_event(logger, logging.WARNING, "invalid_access_token", status_code=401)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        ) from exc
    except AuthenticationConfigurationError as exc:
        log_event(logger, logging.WARNING, "authentication_not_configured", status_code=503)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        ) from exc

    user = db.query(User).filter(User.username == subject).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def user_to_read(user: User) -> UserRead:
    return UserRead(
        id=UUID(user.id),
        username=user.username,
        is_active=user.is_active,
        created_at=user.created_at,
    )
