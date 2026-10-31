"""Tests for manual recovery of interrupted task executions."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from stanford_ai_os.db.models import Base, Task, TaskExecution
from stanford_ai_os.services import task_execution_history_service as history_service


@pytest.fixture
def session(tmp_path: Path):
    db_path = tmp_path / "recovery.db"
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
    task = Task(title="Recovery task", description="Details")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _create_execution(db, task, **overrides) -> TaskExecution:
    values = {
        "task_id": task.id,
        "status": "running",
        "provider": "fake",
        "model": "fake-model",
        "duration_ms": None,
        "error_category": None,
        "started_at": datetime.now(UTC) - timedelta(seconds=5),
        "completed_at": None,
    }
    values.update(overrides)
    execution = TaskExecution(**values)
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def test_recover_running_execution(session) -> None:
    db, _engine = session
    task = _create_task(db)
    execution = _create_execution(db, task)

    recovered = history_service.recover_execution(db, execution.id)

    assert recovered is not None
    assert recovered.id == execution.id
    assert recovered.status == "failure"
    assert recovered.error_category == "interrupted"
    assert recovered.completed_at is not None
    assert recovered.provider == "fake"
    assert recovered.model == "fake-model"
    assert recovered.started_at == execution.started_at
    assert recovered.duration_ms is None


def test_recovered_record_persists(session) -> None:
    db, _engine = session
    task = _create_task(db)
    execution = _create_execution(db, task)

    history_service.recover_execution(db, execution.id)

    persisted = db.get(TaskExecution, execution.id)
    assert persisted is not None
    assert persisted.status == "failure"
    assert persisted.error_category == "interrupted"
    assert persisted.completed_at is not None


def test_success_record_remains_unchanged(session) -> None:
    db, _engine = session
    task = _create_task(db)
    execution = _create_execution(db, task, status="success", completed_at=datetime.now(UTC))

    before_completed_at = execution.completed_at
    recovered = history_service.recover_execution(db, execution.id)

    assert recovered is not None
    assert recovered.status == "success"
    assert recovered.error_category is None
    assert recovered.completed_at == before_completed_at


def test_failure_record_remains_unchanged(session) -> None:
    db, _engine = session
    task = _create_task(db)
    execution = _create_execution(
        db,
        task,
        status="failure",
        error_category="timeout",
        completed_at=datetime.now(UTC),
    )

    recovered = history_service.recover_execution(db, execution.id)

    assert recovered is not None
    assert recovered.status == "failure"
    assert recovered.error_category == "timeout"


def test_missing_execution_returns_none(session) -> None:
    db, _engine = session

    assert history_service.recover_execution(db, uuid.uuid4()) is None


def test_repeated_recovery_is_idempotent(session) -> None:
    db, _engine = session
    task = _create_task(db)
    execution = _create_execution(db, task)

    first = history_service.recover_execution(db, execution.id)
    second = history_service.recover_execution(db, execution.id)

    assert first is not None
    assert second is not None
    assert first.status == "failure"
    assert second.status == "failure"
    assert first.completed_at == second.completed_at
    assert second.error_category == "interrupted"


def test_recovery_does_not_change_task_status(session) -> None:
    db, _engine = session
    task = _create_task(db)
    execution = _create_execution(db, task)

    history_service.recover_execution(db, execution.id)

    refreshed_task = db.get(Task, task.id)
    assert refreshed_task is not None
    assert refreshed_task.status == "pending"


def test_recover_execution_preserves_null_metadata(session) -> None:
    db, _engine = session
    task = _create_task(db)
    execution = _create_execution(
        db,
        task,
        provider=None,
        model=None,
        duration_ms=None,
        started_at=None,
        completed_at=None,
    )

    recovered = history_service.recover_execution(db, execution.id)

    assert recovered is not None
    assert recovered.status == "failure"
    assert recovered.error_category == "interrupted"
    assert recovered.provider is None
    assert recovered.model is None
    assert recovered.duration_ms is None
    assert recovered.started_at is None
    assert recovered.completed_at is not None


def test_recovery_does_not_require_provider() -> None:
    # The function signature has no provider parameter.
    import inspect

    signature = inspect.signature(history_service.recover_execution)
    assert "provider" not in signature.parameters


def test_stale_terminal_state_is_not_overwritten(session) -> None:
    db, engine = session
    task = _create_task(db)
    execution = _create_execution(db, task, status="running")
    execution_id = execution.id

    triggered = {"done": False}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if triggered["done"] or not isinstance(statement, str):
            return
        if not statement.startswith("UPDATE task_executions"):
            return
        triggered["done"] = True
        cursor.execute(
            "UPDATE task_executions SET status = ?, error_category = ?, "
            "completed_at = ? WHERE id = ?",
            ("success", None, datetime.now(UTC).isoformat(), execution_id),
        )

    from sqlalchemy import event

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        recovered = history_service.recover_execution(db, execution_id)
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)

    assert recovered is not None
    assert recovered.status == "success"
    assert recovered.error_category is None
    assert recovered.completed_at is not None

    refreshed = db.get(TaskExecution, execution_id)
    assert refreshed is not None
    assert refreshed.status == "success"
    assert refreshed.error_category is None


def test_concurrent_recovery_from_separate_sessions(tmp_path: Path) -> None:
    db_path = tmp_path / "concurrent_recovery.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    first_session = session_factory()
    second_session = session_factory()
    try:
        task = Task(title="Concurrent recovery task", description="Details")
        first_session.add(task)
        first_session.commit()
        first_session.refresh(task)

        execution = TaskExecution(task_id=task.id, status="running")
        first_session.add(execution)
        first_session.commit()
        first_session.refresh(execution)
        execution_id = execution.id

        first_result = history_service.recover_execution(first_session, execution_id)
        second_result = history_service.recover_execution(second_session, execution_id)

        assert first_result is not None
        assert second_result is not None
        assert first_result.status == "failure"
        assert second_result.status == "failure"
        assert first_result.error_category == "interrupted"
        assert second_result.error_category == "interrupted"

        first_refreshed = first_session.get(TaskExecution, execution_id)
        second_refreshed = second_session.get(TaskExecution, execution_id)
        assert first_refreshed is not None
        assert second_refreshed is not None
        assert first_refreshed.status == "failure"
        assert second_refreshed.status == "failure"
        assert first_refreshed.completed_at == second_refreshed.completed_at
    finally:
        first_session.close()
        second_session.close()
        engine.dispose()


def test_recover_execution_propagates_commit_failure(tmp_path: Path) -> None:
    db_path = tmp_path / "commit_failure.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()

    try:
        task = Task(title="Commit failure task", description="Details")
        db.add(task)
        db.commit()
        db.refresh(task)

        execution = TaskExecution(task_id=task.id, status="running")
        db.add(execution)
        db.commit()
        db.refresh(execution)

        original_commit = db.commit

        def failing_commit() -> None:
            raise RuntimeError("commit failed")

        db.commit = failing_commit
        with pytest.raises(RuntimeError, match="commit failed"):
            history_service.recover_execution(db, execution.id)

        db.commit = original_commit
        db.rollback()

        refreshed = db.get(TaskExecution, execution.id)
        assert refreshed is not None
        assert refreshed.status == "running"
    finally:
        db.close()
        engine.dispose()


def test_recover_execution_does_not_invoke_model_provider() -> None:
    import inspect

    assert "provider" not in inspect.signature(history_service.recover_execution).parameters

    source = inspect.getsource(history_service.recover_execution)
    assert ".generate(" not in source
    assert "get_model_router" not in source
