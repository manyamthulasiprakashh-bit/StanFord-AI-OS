"""Tests for Phase 6 execution-history lifecycle integration."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.test_task_execution import FakeProvider, FakeRouter

from stanford_ai_os.main import app
from stanford_ai_os.modelrouter.providers.base import (
    ProviderConfigurationError,
    ProviderError,
)
from stanford_ai_os.services import task_execution_history_service


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "history_integration.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    with TestClient(app) as test_client:
        login_response = test_client.post(
            "/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client


def _create_task(client: TestClient, title: str = "History lifecycle task") -> dict[str, Any]:
    response = client.post("/tasks", json={"title": title, "description": "Details"})
    assert response.status_code == 201
    return response.json()


def _history(client: TestClient, task_id: str) -> list[dict[str, Any]]:
    response = client.get(f"/tasks/{task_id}/executions")
    assert response.status_code == 200
    return response.json()


def test_successful_execution_creates_running_then_success_history(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 200
    assert response.json()["output"] == "Generated result"
    assert len(provider.calls) == 1

    history = _history(client, created["id"])
    assert len(history) == 1
    record = history[0]
    assert record["status"] == "success"
    assert record["provider"] == "fake"
    assert record["model"] == "fake-model"
    assert record["duration_ms"] is not None
    assert record["duration_ms"] >= 0
    assert record["error_category"] is None
    assert record["completed_at"] is not None
    assert record["started_at"] is not None


def test_provider_failure_creates_failure_history(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider(error=ProviderError("secret provider details"))

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 502
    assert response.json()["detail"] == "Model provider request failed"
    assert len(provider.calls) == 1

    history = _history(client, created["id"])
    assert len(history) == 1
    record = history[0]
    assert record["status"] == "failure"
    assert record["error_category"] == "execution"
    assert record["duration_ms"] is not None
    assert record["duration_ms"] >= 0
    assert record["completed_at"] is not None
    assert "secret provider details" not in str(record)


def test_provider_configuration_failure_is_recorded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)

    class ConfigFailingRouter:
        def get_provider(self):
            raise ProviderConfigurationError("secret configuration details")

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: ConfigFailingRouter(),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 502
    history = _history(client, created["id"])
    assert len(history) == 1
    record = history[0]
    assert record["status"] == "failure"
    assert record["error_category"] == "configuration"
    assert record["provider"] is None
    assert record["model"] is None
    assert "secret configuration details" not in str(record)


def test_history_creation_failure_prevents_provider_call(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_history_service.create_execution",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            task_execution_history_service.TaskExecutionHistoryError("boom")
        ),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 500
    assert response.json()["detail"] == "Execution history could not be recorded"
    assert len(provider.calls) == 0

    history = _history(client, created["id"])
    assert history == []


def test_success_history_update_failure_returns_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider()
    calls: list[dict[str, Any]] = []

    class UpdatedRecord:
        status = "running"
        _transitioned = True

    def fake_update(db, execution_id, **kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise task_execution_history_service.TaskExecutionHistoryError("boom")
        return UpdatedRecord()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_history_service.update_execution",
        fake_update,
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 500
    assert response.json()["detail"] == "Execution history could not be recorded"
    assert len(provider.calls) == 1


def test_failure_history_update_error_does_not_leak_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider(error=ProviderError("secret provider details"))
    calls: list[dict[str, Any]] = []

    class UpdatedRecord:
        status = "running"
        _transitioned = True

    def fake_update(db, execution_id, **kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise task_execution_history_service.TaskExecutionHistoryError("secret update details")
        return UpdatedRecord()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_history_service.update_execution",
        fake_update,
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 502
    assert response.json()["detail"] == "Model provider request failed"
    assert "secret update details" not in response.text
    assert len(provider.calls) == 1


def test_task_status_unchanged_after_integrated_execution(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    before = client.get(f"/tasks/{created['id']}").json()["status"]
    response = client.post(f"/tasks/{created['id']}/execute")
    after = client.get(f"/tasks/{created['id']}").json()["status"]

    assert response.status_code == 200
    assert before == "pending"
    assert after == "pending"


def test_integrated_history_does_not_store_sensitive_values(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client)
    provider = FakeProvider(error=ProviderError("secret provider details"))

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    client.post(f"/tasks/{created['id']}/execute")
    history = _history(client, created["id"])

    assert len(history) == 1
    record = history[0]
    assert "secret provider details" not in str(record)
    assert "output" not in record
    assert "prompt" not in record
