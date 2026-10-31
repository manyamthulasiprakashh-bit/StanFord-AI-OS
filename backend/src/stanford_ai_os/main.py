"""FastAPI application entry point for Stanford-AI OS."""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from stanford_ai_os.api.auth import router as auth_router
from stanford_ai_os.api.task_execution import router as task_execution_router
from stanford_ai_os.api.task_execution_history import router as task_execution_history_router
from stanford_ai_os.api.tasks import router as tasks_router
from stanford_ai_os.config import get_settings
from stanford_ai_os.db.models import Base
from stanford_ai_os.db.session import dispose_shared_engine, get_shared_engine
from stanford_ai_os.observability.context import (
    reset_request_id,
    set_request_id,
)
from stanford_ai_os.observability.logging_config import configure_logging, log_event
from stanford_ai_os.services.auth_service import bootstrap_admin_user

settings = get_settings()
configure_logging()

logger = logging.getLogger(__name__)


def parse_cors_allowed_origins(value: str) -> list[str]:
    """Parse a comma-separated CORS origin list into a clean list."""

    return [origin.strip() for origin in value.split(",") if origin.strip()]


def configure_cors(app: FastAPI, allowed_origins: list[str]) -> None:
    """Add CORSMiddleware when explicit origins are configured."""

    if not allowed_origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.secret_key and len(settings.secret_key) >= 32 and settings.admin_password:
        engine = get_shared_engine()
        Base.metadata.create_all(bind=engine, checkfirst=True)
        with Session(engine) as db:
            bootstrap_admin_user(db)
    yield
    dispose_shared_engine()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

configure_cors(app, parse_cors_allowed_origins(settings.cors_allowed_origins))


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = str(uuid.uuid4())
    token = set_request_id(rid)
    try:
        response = await call_next(request)
    except Exception:
        log_event(logger, logging.ERROR, "unhandled_exception", status_code=500)
        response = Response("Internal Server Error", status_code=500, media_type="text/plain")
    finally:
        reset_request_id(token)
    response.headers["X-Request-ID"] = rid
    return response


app.include_router(auth_router)
app.include_router(tasks_router)
app.include_router(task_execution_router)
app.include_router(task_execution_history_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the application process is running."""

    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
    }
