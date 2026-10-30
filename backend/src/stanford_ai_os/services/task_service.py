"""Task service layer.

This module contains task operations and keeps database access separate from
HTTP route definitions.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from stanford_ai_os.db.models import Task
from stanford_ai_os.schemas.task import TaskCreate, TaskStatus


def create_task(db: Session, task_in: TaskCreate) -> Task:
    task = Task(
        title=task_in.title,
        description=task_in.description,
        status=TaskStatus.pending.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session) -> list[Task]:
    return db.query(Task).order_by(Task.created_at.desc()).all()


def get_task(db: Session, task_id: UUID) -> Task | None:
    return db.get(Task, str(task_id))
