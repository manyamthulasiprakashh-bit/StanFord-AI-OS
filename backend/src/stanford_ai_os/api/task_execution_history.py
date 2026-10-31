"""Task execution history REST API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from stanford_ai_os.db.models import Task
from stanford_ai_os.db.session import get_db
from stanford_ai_os.schemas.task_execution_history import TaskExecutionHistoryRead
from stanford_ai_os.services import task_execution_history_service
from stanford_ai_os.services.auth_service import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["task-execution-history"])


@router.get("/tasks/{task_id}/executions", response_model=list[TaskExecutionHistoryRead])
def list_task_executions(
    task_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[TaskExecutionHistoryRead]:
    task = db.get(Task, str(task_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_execution_history_service.list_executions(
        db, task_id, limit=limit, offset=offset
    )


@router.get("/executions/{execution_id}", response_model=TaskExecutionHistoryRead)
def get_task_execution(
    execution_id: UUID, db: Session = Depends(get_db)
) -> TaskExecutionHistoryRead:
    execution = task_execution_history_service.get_execution(db, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution
