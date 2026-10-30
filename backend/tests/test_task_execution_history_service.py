"""Tests for the task execution history persistence service."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from stanford_ai_os.db.models import Base, Task, TaskExecution
from stanford_ai_os.services import task_execution_history_service as history_service


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "history_service.db"


@pytest.fixture
def engine(db_path: Path):
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def _create_task(db) -> Task:
    task = Task(title="History service task", description="Details")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_create_execution_persists_record(session) -> None:
    task = _create_task(session)

    execution = history_service.create_execution(
        session,
        task_id=task.id,
        status="success",
        provider="fake",
        model="fake-model",
        duration_ms=42,
        error_category=None,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    assert execution.id is not None
    assert execution.task_id == task.id
    assert execution.status == "success"
    assert execution.provider == "fake"
    assert execution.model == "fake-model"
    assert execution.duration_ms == 42


def test_created_execution_has_generated_id(session) -> None:
    task = _create_task(session)

    execution = history_service.create_execution(session, task_id=task.id, status="running")

    uuid.UUID(execution.id)


def test_creation_timestamp_populated(session) -> None:
    task = _create_task(session)

    execution = history_service.create_execution(session, task_id=task.id, status="running")

    assert execution.created_at is not None


def test_optional_metadata_can_be_null(session) -> None:
    task = _create_task(session)

    execution = history_service.create_execution(
        session,
        task_id=task.id,
        status="failure",
        provider=None,
        model=None,
        duration_ms=None,
        error_category=None,
        started_at=None,
        completed_at=None,
    )

    assert execution.provider is None
    assert execution.model is None
    assert execution.duration_ms is None
    assert execution.error_category is None
    assert execution.started_at is None
    assert execution.completed_at is None


def test_supplied_metadata_is_persisted(session) -> None:
    task = _create_task(session)

    execution = history_service.create_execution(
        session,
        task_id=task.id,
        status="failure",
        provider="nvidia",
        model="meta/llama-3.3-70b-instruct",
        duration_ms=7,
        error_category="timeout",
    )

    retrieved = session.get(TaskExecution, execution.id)

    assert retrieved is not None
    assert retrieved.status == "failure"
    assert retrieved.provider == "nvidia"
    assert retrieved.model == "meta/llama-3.3-70b-instruct"
    assert retrieved.duration_ms == 7
    assert retrieved.error_category == "timeout"


def test_get_execution_returns_record(session) -> None:
    task = _create_task(session)
    created = history_service.create_execution(session, task_id=task.id, status="success")

    retrieved = history_service.get_execution(session, created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.task_id == task.id
    assert retrieved.status == "success"


def test_get_unknown_execution_returns_none(session) -> None:
    result = history_service.get_execution(session, uuid.uuid4())

    assert result is None


def test_retrieval_does_not_modify_record(session) -> None:
    task = _create_task(session)
    created = history_service.create_execution(
        session, task_id=task.id, status="success", duration_ms=5
    )

    retrieved = history_service.get_execution(session, created.id)

    assert retrieved is not None
    assert retrieved.status == "success"
    assert retrieved.duration_ms == 5
    session.rollback()
    unchanged = session.get(TaskExecution, created.id)
    assert unchanged is not None
    assert unchanged.status == "success"
    assert unchanged.duration_ms == 5


def test_session_lifecycle_persists_across_sessions(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    first_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    try:
        task = Task(title="Persisted task", description="Details")
        first_session.add(task)
        first_session.commit()
        first_session.refresh(task)

        execution = history_service.create_execution(
            first_session, task_id=task.id, status="success", duration_ms=9
        )
        execution_id = execution.id
    finally:
        first_session.close()

    second_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        retrieved = history_service.get_execution(second_session, execution_id)
        assert retrieved is not None
        assert retrieved.status == "success"
        assert retrieved.duration_ms == 9
    finally:
        second_session.close()
        engine.dispose()
