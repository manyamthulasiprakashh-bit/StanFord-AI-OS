"""Tests for the Phase 4 single-pass task execution service."""

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from stanford_ai_os.db.models import Base
from stanford_ai_os.db.session import get_engine
from stanford_ai_os.main import app
from stanford_ai_os.modelrouter.providers.base import ProviderError
from stanford_ai_os.modelrouter.types import ModelRequest, ModelResponse
from stanford_ai_os.schemas.task import TaskCreate
from stanford_ai_os.services import task_execution_service, task_service


class FakeProvider:
    def __init__(
        self,
        response: ModelResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response or ModelResponse(
            text="Generated result", provider="fake", model="fake-model"
        )
        self.error = error
        self.calls: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.response


class FakeRouter:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider

    def get_provider(self) -> FakeProvider:
        return self.provider


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "tasks.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    with TestClient(app) as test_client:
        yield test_client


def _create_task(client: TestClient, title: str, description: str | None) -> dict[str, Any]:
    response = client.post("/tasks", json={"title": title, "description": description})
    assert response.status_code == 201
    return response.json()


def test_successful_task_execution(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    created = _create_task(client, "Summarize notes", "Important details")
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == created["id"]
    assert data["output"] == "Generated result"
    assert data["provider"] == "fake"
    assert data["model"] == "fake-model"
    assert len(provider.calls) == 1


def test_execution_request_contains_task_content(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Review report", "Check the numbers")
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    client.post(f"/tasks/{created['id']}/execute")

    request = provider.calls[0]
    assert "Review report" in request.prompt
    assert "Check the numbers" in request.prompt
    assert request.system is not None
    assert "untrusted data" in request.system


def test_missing_task_returns_404(client: TestClient) -> None:
    response = client.post(f"/tasks/{uuid.uuid4()}/execute")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_provider_failure_returns_safe_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Failing task", "Details")
    provider = FakeProvider(error=ProviderError("secret provider details"))

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 502
    assert response.json()["detail"] == "Model provider request failed"
    assert "secret provider details" not in response.text


def test_task_status_unchanged_after_execution(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Status task", "Details")
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


def test_task_remains_retrievable_after_execution(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Retrievable task", "Details")
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    client.post(f"/tasks/{created['id']}/execute")
    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Retrievable task"


def test_existing_task_crud_behavior_remains_intact(client: TestClient) -> None:
    created = _create_task(client, "CRUD task", "Details")
    listed = client.get("/tasks")
    retrieved = client.get(f"/tasks/{created['id']}")

    assert listed.status_code == 200
    assert any(task["id"] == created["id"] for task in listed.json())
    assert retrieved.status_code == 200


def test_execute_task_service_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "service.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        task = task_service.create_task(db, TaskCreate(title="Service task", description="Details"))
        provider = FakeProvider()
        result = task_execution_service.execute_task(db, uuid.UUID(task.id), provider=provider)

        assert result.task_id == uuid.UUID(task.id)
        assert result.output == "Generated result"
        assert result.provider == "fake"
        assert result.model == "fake-model"
        assert len(provider.calls) == 1
    finally:
        db.close()
        engine.dispose()


def test_execute_task_service_missing_task(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        with pytest.raises(task_execution_service.TaskNotFoundError):
            task_execution_service.execute_task(db, uuid.uuid4(), provider=FakeProvider())
    finally:
        db.close()
        engine.dispose()


def test_execute_task_service_provider_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "provider.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    try:
        task = task_service.create_task(db, TaskCreate(title="Error task", description="Details"))
        provider = FakeProvider(error=ProviderError("secret provider details"))
        with pytest.raises(task_execution_service.TaskExecutionError) as exc_info:
            task_execution_service.execute_task(db, uuid.UUID(task.id), provider=provider)

        assert "secret provider details" not in str(exc_info.value)
    finally:
        db.close()
        engine.dispose()
