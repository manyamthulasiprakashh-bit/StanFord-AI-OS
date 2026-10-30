"""Focused reliability tests for task execution finalization."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.test_task_execution import FakeProvider, FakeRouter

from stanford_ai_os.db.models import Base
from stanford_ai_os.main import app
from stanford_ai_os.modelrouter.router import UnsupportedProviderError
from stanford_ai_os.services import task_execution_history_service


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "reliability.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    with TestClient(app) as test_client:
        yield test_client


def _create_task(client: TestClient) -> dict[str, Any]:
    response = client.post("/tasks", json={"title": "Reliability task", "description": "Details"})
    assert response.status_code == 201
    return response.json()


def test_terminal_state_already_established_before_success_finalization(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider()
    running_id: dict[str, str] = {}

    original_create = task_execution_history_service.create_execution

    def create_side_effect(db, **kwargs):
        record = original_create(db, **kwargs)
        running_id["id"] = record.id
        return record

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_history_service.create_execution",
        create_side_effect,
    )

    # Directly mark the running record terminal before finalization.
    original_generate = provider.generate

    def generate_with_terminal_record(request):
        db_url = client.headers.get("x-unused", "")
        _ = db_url
        # The test fixture's database path is available through the client's
        # environment; use the same path configured for this test client.
        import os

        engine = create_engine(os.environ["STANFORD_AI_OS_DATABASE_URL"], future=True)
        Base.metadata.create_all(bind=engine, checkfirst=True)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = session_factory()
        try:
            task_execution_history_service.update_execution(
                db,
                running_id["id"],
                status="success",
                provider="existing-provider",
                model="existing-model",
                duration_ms=999,
                error_category=None,
                completed_at=datetime.now(UTC),
            )
        finally:
            db.close()
            engine.dispose()
        return original_generate(request)

    provider.generate = generate_with_terminal_record

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 500
    assert response.json()["detail"] == "Execution history could not be recorded"
    assert len(provider.calls) == 1

    history = client.get(f"/tasks/{created['id']}/executions").json()
    assert len(history) == 1
    record = history[0]
    assert record["status"] == "success"
    assert record["provider"] == "existing-provider"
    assert record["model"] == "existing-model"
    assert record["duration_ms"] == 999


def test_recovery_and_execution_completion_do_not_overwrite_terminal_state(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider()
    running_id: dict[str, str] = {}

    original_create = task_execution_history_service.create_execution

    def create_side_effect(db, **kwargs):
        record = original_create(db, **kwargs)
        running_id["id"] = record.id
        return record

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_history_service.create_execution",
        create_side_effect,
    )

    original_generate = provider.generate

    def generate_with_recovery(request):
        import os

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(os.environ["STANFORD_AI_OS_DATABASE_URL"], future=True)
        Base.metadata.create_all(bind=engine, checkfirst=True)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = session_factory()
        try:
            task_execution_history_service.recover_execution(db, running_id["id"])
        finally:
            db.close()
            engine.dispose()
        return original_generate(request)

    provider.generate = generate_with_recovery

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 500
    assert response.json()["detail"] == "Execution history could not be recorded"
    assert len(provider.calls) == 1

    history = client.get(f"/tasks/{created['id']}/executions").json()
    assert len(history) == 1
    record = history[0]
    assert record["status"] == "failure"
    assert record["error_category"] == "interrupted"


def test_unsupported_provider_configuration_returns_502_and_failure_history(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)

    class UnsupportedRouter:
        def get_provider(self):
            raise UnsupportedProviderError("secret provider name")

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: UnsupportedRouter(),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 502
    assert response.json()["detail"] == "Model provider request failed"
    assert "secret provider name" not in response.text

    history = client.get(f"/tasks/{created['id']}/executions").json()
    assert len(history) == 1
    record = history[0]
    assert record["status"] == "failure"
    assert record["error_category"] == "configuration"
    assert record["provider"] is None
    assert record["model"] is None
