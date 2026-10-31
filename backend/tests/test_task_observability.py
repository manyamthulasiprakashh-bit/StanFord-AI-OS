"""Tests for Phase 5 execution observability."""

import logging
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from tests.test_task_execution import FakeProvider, FakeRouter

from stanford_ai_os.main import app
from stanford_ai_os.modelrouter.providers.base import ProviderError
from stanford_ai_os.observability.execution import ExecutionMetrics
from stanford_ai_os.services.task_execution_service import (
    TaskExecutionError,
    TaskNotFoundError,
    execute_task,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "tasks.db"
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


def _create_task(client: TestClient, title: str, description: str | None) -> dict[str, Any]:
    response = client.post("/tasks", json={"title": title, "description": description})
    assert response.status_code == 201
    return response.json()


def test_successful_execution_records_one_observation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Observable task", "Details")
    provider = FakeProvider()
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute", json={}) if False else client.post(
        f"/tasks/{created['id']}/execute"
    )

    assert response.status_code == 200
    # Re-run through service-level observer by calling the endpoint is already done;
    # use a direct service call for exact observer capture.
    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        result_provider = FakeProvider()
        captured: list[Any] = []
        execute_task(
            db,
            __import__("uuid").UUID(created["id"]),
            provider=result_provider,
            observer=captured.append,
        )
        assert len(captured) == 1
        observation = captured[0]
        assert observation.outcome == "success"
        assert observation.error_category is None
        assert observation.duration_ms >= 0
        assert observation.provider == "fake"
        assert observation.model == "fake-model"
        assert len(result_provider.calls) == 1
    finally:
        db.close()
        engine.dispose()


def test_failed_execution_records_one_observation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Failing observable task", "Details")
    provider = FakeProvider(error=ProviderError("secret provider details"))
    captured: list[Any] = []

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    # Direct service call gives precise observer capture.
    import uuid

    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        task_provider = FakeProvider(error=ProviderError("secret provider details"))
        with pytest.raises(TaskExecutionError):
            execute_task(
                db,
                uuid.UUID(created["id"]),
                provider=task_provider,
                observer=captured.append,
            )
        assert len(captured) == 1
        observation = captured[0]
        assert observation.outcome == "failure"
        assert observation.error_category == "execution"
        assert observation.duration_ms >= 0
        assert "secret provider details" not in str(observation)
    finally:
        db.close()
        engine.dispose()


def test_missing_task_category(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "missing.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        captured: list[Any] = []
        with pytest.raises(TaskNotFoundError):
            execute_task(db, uuid.uuid4(), provider=FakeProvider(), observer=captured.append)
        assert len(captured) == 1
        assert captured[0].error_category == "task_not_found"
        assert captured[0].outcome == "failure"
        assert captured[0].duration_ms >= 0
    finally:
        db.close()
        engine.dispose()


def test_provider_failure_category(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine
    from stanford_ai_os.modelrouter.providers.base import (
        ProviderAuthenticationError,
        ProviderConfigurationError,
        ProviderConnectionError,
        ProviderRateLimitError,
        ProviderResponseError,
        ProviderTimeoutError,
    )
    from stanford_ai_os.schemas.task import TaskCreate
    from stanford_ai_os.services import task_service

    cases = [
        (ProviderConfigurationError("x"), "configuration"),
        (ProviderAuthenticationError("x"), "authentication"),
        (ProviderRateLimitError("x"), "rate_limit"),
        (ProviderTimeoutError("x"), "timeout"),
        (ProviderConnectionError("x"), "connection"),
        (ProviderResponseError("x"), "response"),
    ]

    for error, expected_category in cases:
        db_path = tmp_path / f"{expected_category}.db"
        monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        try:
            task = task_service.create_task(db, TaskCreate(title="Task", description="Details"))
            provider = FakeProvider(error=error)
            captured: list[Any] = []
            with pytest.raises(TaskExecutionError):
                execute_task(db, uuid.UUID(task.id), provider=provider, observer=captured.append)
            assert captured[0].error_category == expected_category
        finally:
            db.close()
            engine.dispose()


def test_duration_returned_in_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Timed task", "Details")
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 200
    assert isinstance(response.json()["duration_ms"], int)
    assert response.json()["duration_ms"] >= 0


def test_observer_failure_does_not_replace_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "observer-success.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine
    from stanford_ai_os.schemas.task import TaskCreate
    from stanford_ai_os.services import task_service

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        task = task_service.create_task(
            db, TaskCreate(title="Observer task", description="Details")
        )
        provider = FakeProvider()

        def failing_observer(observation: Any) -> None:
            raise RuntimeError("observer failed")

        result = execute_task(
            db,
            uuid.UUID(task.id),
            provider=provider,
            observer=failing_observer,
        )

        assert result.output == "Generated result"
        assert len(provider.calls) == 1
    finally:
        db.close()
        engine.dispose()


def test_observer_failure_does_not_conceal_original_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "observer-failure.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine
    from stanford_ai_os.schemas.task import TaskCreate
    from stanford_ai_os.services import task_service

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    try:
        task = task_service.create_task(
            db, TaskCreate(title="Observer task", description="Details")
        )
        provider = FakeProvider(error=ProviderError("secret provider details"))

        def failing_observer(observation: Any) -> None:
            raise RuntimeError("observer failed")

        with pytest.raises(TaskExecutionError):
            execute_task(
                db,
                uuid.UUID(task.id),
                provider=provider,
                observer=failing_observer,
            )
    finally:
        db.close()
        engine.dispose()


def test_default_logging_does_not_expose_sensitive_content(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = _create_task(client, "Logging task", "secret task details")
    provider = FakeProvider(error=ProviderError("secret provider details"))

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    with caplog.at_level(logging.INFO):
        response = client.post(f"/tasks/{created['id']}/execute")

    assert response.status_code == 502
    assert "secret task details" not in caplog.text
    assert "secret provider details" not in caplog.text


def test_task_status_unchanged_after_observable_execution(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Status task", "Details")
    provider = FakeProvider()

    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    before = client.get(f"/tasks/{created['id']}").json()["status"]
    client.post(f"/tasks/{created['id']}/execute")
    after = client.get(f"/tasks/{created['id']}").json()["status"]

    assert before == "pending"
    assert after == "pending"


def test_bounded_in_memory_history() -> None:
    metrics = ExecutionMetrics(max_observations=2)
    from stanford_ai_os.observability.execution import ExecutionObservation

    for _ in range(3):
        metrics(
            ExecutionObservation(
                task_id=uuid.uuid4(),
                provider="fake",
                model="fake-model",
                duration_ms=1,
                outcome="success",
            )
        )

    assert len(metrics) == 2
    assert len(metrics.observations) == 2
