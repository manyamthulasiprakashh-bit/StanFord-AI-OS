"""Tests for the TaskExecution database model."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from stanford_ai_os.db.models import Base, Task, TaskExecution


@pytest.fixture
def session(tmp_path: Path):
    db_path = tmp_path / "task_execution_model.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db, engine
    finally:
        db.close()
        engine.dispose()


def _create_task(db) -> Task:
    task = Task(title="Model test task", description="Details")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_valid_execution_record_can_be_inserted_and_retrieved(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(
        task_id=task.id,
        status="running",
        provider="fake",
        model="fake-model",
        duration_ms=12,
        error_category=None,
        started_at=datetime.now(UTC),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    retrieved = db.get(TaskExecution, execution.id)

    assert retrieved is not None
    assert retrieved.task_id == task.id
    assert retrieved.status == "running"
    assert retrieved.provider == "fake"
    assert retrieved.model == "fake-model"
    assert retrieved.duration_ms == 12
    assert retrieved.error_category is None


def test_uuid_generated_automatically(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(task_id=task.id, status="success")
    db.add(execution)
    db.commit()

    assert execution.id
    uuid.UUID(execution.id)


def test_creation_timestamp_received(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(task_id=task.id, status="running")
    db.add(execution)
    db.commit()
    db.refresh(execution)

    assert execution.created_at is not None


def test_nullable_metadata_fields_accept_null(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(
        task_id=task.id,
        status="failure",
        provider=None,
        model=None,
        duration_ms=None,
        error_category=None,
        started_at=None,
        completed_at=None,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    assert execution.provider is None
    assert execution.model is None
    assert execution.duration_ms is None
    assert execution.error_category is None
    assert execution.started_at is None
    assert execution.completed_at is None


@pytest.mark.parametrize("status", ["running", "success", "failure"])
def test_database_accepts_valid_statuses(session, status: str) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(task_id=task.id, status=status)
    db.add(execution)
    db.commit()

    assert db.get(TaskExecution, execution.id).status == status


def test_database_rejects_invalid_status(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(task_id=task.id, status="unknown")
    db.add(execution)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_database_rejects_negative_duration(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(task_id=task.id, status="failure", duration_ms=-1)
    db.add(execution)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_database_accepts_null_duration(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(task_id=task.id, status="running", duration_ms=None)
    db.add(execution)
    db.commit()

    assert db.get(TaskExecution, execution.id).duration_ms is None


def test_model_references_existing_task(session) -> None:
    db, _engine = session
    task = _create_task(db)

    execution = TaskExecution(task_id=task.id, status="running")
    db.add(execution)
    db.commit()
    db.refresh(execution)

    assert execution.task_id == task.id


def test_composite_history_index_present_in_metadata() -> None:
    table = TaskExecution.__table__
    index_names = {index.name for index in table.indexes}
    composite_index = next(
        index
        for index in table.indexes
        if {column.name for column in index.columns} == {"task_id", "created_at"}
    )

    assert "ix_task_executions_task_id_created_at" in index_names
    assert composite_index is not None
