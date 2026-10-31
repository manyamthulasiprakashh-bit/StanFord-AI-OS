"""Persistence helpers for task execution history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from stanford_ai_os.db.models import TaskExecution
from stanford_ai_os.observability.logging_config import log_event

logger = logging.getLogger(__name__)


def create_execution(
    db: Session,
    *,
    task_id: UUID | str,
    status: str,
    provider: str | None = None,
    model: str | None = None,
    duration_ms: int | None = None,
    error_category: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> TaskExecution:
    """Create and persist one execution-history record."""

    execution = TaskExecution(
        task_id=str(task_id),
        status=status,
        provider=provider,
        model=model,
        duration_ms=duration_ms,
        error_category=error_category,
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    execution._transitioned = True
    return execution


def get_execution(db: Session, execution_id: UUID | str) -> TaskExecution | None:
    """Retrieve one execution-history record by ID."""

    return db.get(TaskExecution, str(execution_id))


_UNSET = object()


def update_execution(
    db: Session,
    execution_id: UUID | str,
    *,
    status: str | object = _UNSET,
    provider: str | None | object = _UNSET,
    model: str | None | object = _UNSET,
    duration_ms: int | None | object = _UNSET,
    error_category: str | None | object = _UNSET,
    started_at: datetime | None | object = _UNSET,
    completed_at: datetime | None | object = _UNSET,
) -> TaskExecution | None:
    """Update lifecycle metadata for one execution-history record.

    Fields that are not provided are left unchanged. ``None`` is a valid value
    for nullable fields and clears the previous value.
    """

    execution = db.get(TaskExecution, str(execution_id))
    if execution is None:
        return None

    if status is not _UNSET:
        # A status change is a lifecycle transition. Make it conditional so a
        # stale or concurrent update cannot overwrite an already-terminal row.
        values = {"status": status}
        if provider is not _UNSET:
            values["provider"] = provider
        if model is not _UNSET:
            values["model"] = model
        if duration_ms is not _UNSET:
            values["duration_ms"] = duration_ms
        if error_category is not _UNSET:
            values["error_category"] = error_category
        if started_at is not _UNSET:
            values["started_at"] = started_at
        if completed_at is not _UNSET:
            values["completed_at"] = completed_at

        result = db.execute(
            update(TaskExecution)
            .where(
                TaskExecution.id == str(execution_id),
                TaskExecution.status == "running",
            )
            .values(**values)
        )
        if result.rowcount not in (0, 1):
            raise RuntimeError("Unexpected number of execution rows updated")

        db.commit()
        db.expire_all()
        execution = db.get(TaskExecution, str(execution_id))
        if execution is not None:
            execution._transitioned = result.rowcount == 1
        return execution

    # Metadata-only updates are also conditional. A terminal record must not be
    # modified by a stale or late metadata update.
    values = {}
    if provider is not _UNSET:
        values["provider"] = provider
    if model is not _UNSET:
        values["model"] = model
    if duration_ms is not _UNSET:
        values["duration_ms"] = duration_ms
    if error_category is not _UNSET:
        values["error_category"] = error_category
    if started_at is not _UNSET:
        values["started_at"] = started_at
    if completed_at is not _UNSET:
        values["completed_at"] = completed_at

    if values:
        result = db.execute(
            update(TaskExecution)
            .where(
                TaskExecution.id == str(execution_id),
                TaskExecution.status == "running",
            )
            .values(**values)
        )
        if result.rowcount not in (0, 1):
            raise RuntimeError("Unexpected number of execution rows updated")

        db.commit()
        db.expire_all()
        execution = db.get(TaskExecution, str(execution_id))
        if execution is not None:
            execution._transitioned = result.rowcount == 1
        return execution

    db.commit()
    db.refresh(execution)
    execution._transitioned = True
    return execution


class TaskExecutionHistoryError(Exception):
    """Raised when an execution-history record cannot be persisted."""


def list_executions(
    db: Session,
    task_id: UUID | str,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[TaskExecution]:
    """List execution-history records for a task, newest first."""

    return (
        db.query(TaskExecution)
        .filter(TaskExecution.task_id == str(task_id))
        .order_by(TaskExecution.created_at.desc(), TaskExecution.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# Compatibility aliases for tests or callers using alternate names.
list_task_executions = list_executions


def recover_execution(db: Session, execution_id: UUID | str) -> TaskExecution | None:
    """Mark a confirmed interrupted ``running`` execution as failed.

    This is an explicit, manual recovery operation. It does not call a model
    provider, retry the task, or modify the associated task.

    ``duration_ms`` is intentionally left unchanged. The existing
    ``started_at`` value records when the execution attempt began, while
    ``duration_ms`` measures the provider call. Recovery has no provider call
    and cannot calculate a provider duration consistently, so inventing one
    would change the meaning of the field.
    """

    execution_id_str = str(execution_id)
    completed_at = datetime.now(UTC)

    # The condition is part of the UPDATE itself, so a stale in-memory object
    # cannot turn this into an unconditional overwrite of a terminal state.
    result = db.execute(
        update(TaskExecution)
        .where(
            TaskExecution.id == execution_id_str,
            TaskExecution.status == "running",
        )
        .values(
            status="failure",
            error_category="interrupted",
            completed_at=completed_at,
        )
    )

    if result.rowcount not in (0, 1):
        raise RuntimeError("Unexpected number of execution rows updated")

    db.commit()

    # Clear stale ORM state before reloading the authoritative database row.
    db.expire_all()
    reloaded = db.get(TaskExecution, execution_id_str)
    if result.rowcount == 1 and reloaded is not None:
        log_event(
            logger,
            logging.INFO,
            "execution_recovered",
            execution_id=execution_id_str,
            task_id=reloaded.task_id,
            error_category="interrupted",
        )
    return reloaded


# Compatibility aliases for tests or callers using alternate names.
recover_interrupted_execution = recover_execution
mark_execution_interrupted = recover_execution
mark_execution_as_interrupted = recover_execution
interrupt_execution = recover_execution

# Compatibility aliases for tests or callers using alternate names.
create_task_execution = create_execution
get_task_execution = get_execution
update_task_execution = update_execution
record_execution = create_execution
