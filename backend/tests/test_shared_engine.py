"""Tests for the shared SQLAlchemy engine lifecycle."""

from pathlib import Path

import pytest
from sqlalchemy import text

from stanford_ai_os.db.session import (
    dispose_shared_engine,
    get_engine,
    get_shared_engine,
)


def test_shared_engine_reused_for_same_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "shared.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    first = get_shared_engine()
    second = get_shared_engine()

    assert first is second
    dispose_shared_engine()


def test_shared_engine_changes_with_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path_one = tmp_path / "one.db"
    db_path_two = tmp_path / "two.db"

    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path_one}")
    first = get_shared_engine()

    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path_two}")
    second = get_shared_engine()

    assert first is not second
    dispose_shared_engine()


def test_dispose_shared_engine_clears_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "dispose.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    first = get_shared_engine()
    dispose_shared_engine()
    second = get_shared_engine()

    assert first is not second
    dispose_shared_engine()


def test_direct_get_engine_still_creates_fresh_engines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "direct.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    first = get_engine()
    second = get_engine()

    assert first is not second
    first.dispose()
    second.dispose()


def test_shared_engine_enables_sqlite_foreign_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "fk.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_shared_engine()
    try:
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    finally:
        dispose_shared_engine()
