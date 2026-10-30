"""Task execution REST API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from stanford_ai_os.db.session import get_db
from stanford_ai_os.schemas.task_execution import TaskExecutionResult
from stanford_ai_os.services import task_execution_history_service, task_execution_service

router = APIRouter(prefix="/tasks", tags=["task-execution"])


@router.post("/{task_id}/execute", response_model=TaskExecutionResult)
def execute_task(task_id: UUID, db: Session = Depends(get_db)) -> TaskExecutionResult:
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
