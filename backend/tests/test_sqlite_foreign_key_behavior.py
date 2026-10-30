"""Tests documenting SQLite foreign-key behavior in Stanford-AI OS."""

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from stanford_ai_os.db.models import Base, Task, TaskExecution
from stanford_ai_os.db.session import get_engine


def test_get_engine_enables_sqlite_foreign_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "fk_enabled.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_engine()
    try:
        with engine.connect() as connection:
            foreign_keys_enabled = connection.execute(
                text("PRAGMA foreign_keys")
            ).scalar_one()
        assert foreign_keys_enabled == 1
    finally:
        engine.dispose()


def test_deleting_task_cascades_to_executions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "fk_cascade.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()

    try:
        task = Task(title="Task with history", description="Details")
        db.add(task)
        db.commit()
        db.refresh(task)

        execution = TaskExecution(task_id=task.id, status="success")
        db.add(execution)
        db.commit()
        db.refresh(execution)
        execution_id = execution.id

        db.delete(task)
        db.commit()

        assert db.get(TaskExecution, execution_id) is None
    finally:
        db.close()
        engine.dispose()


def test_execution_requires_existing_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "fk_invalid.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()

    try:
        execution = TaskExecution(task_id=str(__import__("uuid").uuid4()), status="success")
        db.add(execution)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
        engine.dispose()
