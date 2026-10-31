"""Authentication REST API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from stanford_ai_os.db.session import get_db
from stanford_ai_os.observability.logging_config import log_event
from stanford_ai_os.schemas.auth import LoginRequest, TokenResponse, UserRead
from stanford_ai_os.services.auth_service import (
    User,
    check_login_rate_limit,
    create_access_token,
    get_current_user,
    get_settings,
    user_to_read,
    verify_password,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    if not settings.secret_key or len(settings.secret_key) < 32 or not settings.admin_password:
        log_event(logger, logging.WARNING, "authentication_not_configured", status_code=503)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    client_key = request.client.host if request.client is not None else "unknown"
    if not check_login_rate_limit(client_key):
        log_event(logger, logging.WARNING, "login_rate_limited", status_code=429)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts",
        )

    user = db.query(User).filter(User.username == credentials.username).first()
    if user is None:
        password_is_valid = False
    else:
        password_is_valid = verify_password(credentials.password, user.password_hash)
    if user is None or not user.is_active or not password_is_valid:
        log_event(logger, logging.WARNING, "login_failed", status_code=401)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    log_event(logger, logging.INFO, "login_succeeded", status_code=200)
    access_token = create_access_token(user.username)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return user_to_read(current_user)
