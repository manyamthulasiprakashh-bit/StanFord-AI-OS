"""Task execution REST API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from stanford_ai_os.db.models import User
from stanford_ai_os.db.session import get_db
from stanford_ai_os.observability.logging_config import log_event
from stanford_ai_os.schemas.task_execution import TaskExecutionResult
from stanford_ai_os.services import task_execution_history_service, task_execution_service
from stanford_ai_os.services.auth_service import (
    check_execution_rate_limit,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["task-execution"])


@router.post("/{task_id}/execute", response_model=TaskExecutionResult)
def execute_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskExecutionResult:
    if not check_execution_rate_limit(current_user.username):
        log_event(
            logger,
            logging.WARNING,
            "execution_rate_limited",
            task_id=task_id,
            status_code=429,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many execution requests",
        )
    try:
        return task_execution_service.execute_task(db, task_id)
    except task_execution_service.TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except task_execution_service.TaskExecutionError as exc:
        raise HTTPException(status_code=502, detail="Model provider request failed") from exc
    except task_execution_history_service.TaskExecutionHistoryError as exc:
        raise HTTPException(
            status_code=500, detail="Execution history could not be recorded"
        ) from exc
