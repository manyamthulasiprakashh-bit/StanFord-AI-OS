"""Task REST API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from stanford_ai_os.db.session import get_db
from stanford_ai_os.schemas.task import TaskCreate, TaskRead
from stanford_ai_os.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=201)
def create_task(task_in: TaskCreate, db: Session = Depends(get_db)) -> TaskRead:
    task = task_service.create_task(db, task_in)
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)) -> list[TaskRead]:
    return task_service.list_tasks(db)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, db: Session = Depends(get_db)) -> TaskRead:
    task = task_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
