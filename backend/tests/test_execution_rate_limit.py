"""Tests for execution request rate limiting."""

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from stanford_ai_os.main import app
from stanford_ai_os.services.auth_service import (
    check_execution_rate_limit,
    reset_execution_rate_limits,
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "rate_limit.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("STANFORD_AI_OS_EXECUTION_RATE_LIMIT_ATTEMPTS", "2")
    monkeypatch.setenv("STANFORD_AI_OS_EXECUTION_RATE_LIMIT_WINDOW_SECONDS", "60")

    with TestClient(app) as test_client:
        login_response = test_client.post(
            "/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client


def _create_task(client: TestClient) -> dict[str, Any]:
    response = client.post("/tasks", json={"title": "Rate limited task", "description": "Details"})
    assert response.status_code == 201
    return response.json()


def test_execution_requests_below_limit_succeed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_task_execution import FakeProvider, FakeRouter

    created = _create_task(client)
    provider = FakeProvider()
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    first = client.post(f"/tasks/{created['id']}/execute")
    second = client.post(f"/tasks/{created['id']}/execute")

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(provider.calls) == 2


def test_execution_request_exceeding_limit_returns_429(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_task_execution import FakeProvider, FakeRouter

    created = _create_task(client)
    provider = FakeProvider()
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    client.post(f"/tasks/{created['id']}/execute")
    client.post(f"/tasks/{created['id']}/execute")
    rejected = client.post(f"/tasks/{created['id']}/execute")

    assert rejected.status_code == 429
    assert rejected.json() == {"detail": "Too many execution requests"}
    assert len(provider.calls) == 2

    history = client.get(f"/tasks/{created['id']}/executions").json()
    assert len(history) == 2

    task = client.get(f"/tasks/{created['id']}").json()
    assert task["status"] == "pending"


def test_execution_rate_limit_window_expires(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.test_task_execution import FakeProvider, FakeRouter

    created = _create_task(client)
    provider = FakeProvider()
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    monkeypatch.setattr(
        "stanford_ai_os.services.auth_service.time.monotonic", lambda: 100.0
    )
    first = client.post(f"/tasks/{created['id']}/execute")
    assert first.status_code == 200
    second = client.post(f"/tasks/{created['id']}/execute")
    assert second.status_code == 200

    monkeypatch.setattr(
        "stanford_ai_os.services.auth_service.time.monotonic", lambda: 100.5
    )
    blocked_before_expiry = client.post(f"/tasks/{created['id']}/execute")
    assert blocked_before_expiry.status_code == 429

    monkeypatch.setattr(
        "stanford_ai_os.services.auth_service.time.monotonic", lambda: 160.1
    )
    allowed_after_expiry = client.post(f"/tasks/{created['id']}/execute")
    assert allowed_after_expiry.status_code == 200


def test_missing_token_returns_401_not_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "unauthenticated.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")

    with TestClient(app) as client:
        response = client.post(f"/tasks/{uuid.uuid4()}/execute")

    assert response.status_code == 401


def test_invalid_token_returns_401_not_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "invalid-token.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")

    with TestClient(app) as client:
        response = client.post(
            f"/tasks/{uuid.uuid4()}/execute",
            headers={"Authorization": "Bearer not-a-token"},
        )

    assert response.status_code == 401


def test_execution_rate_limit_concurrent_checks() -> None:
    reset_execution_rate_limits()
    allowed_first = check_execution_rate_limit(
        "concurrent-user", now=100.0, max_attempts=2, window_seconds=10
    )
    allowed_second = check_execution_rate_limit(
        "concurrent-user", now=100.0, max_attempts=2, window_seconds=10
    )
    blocked = check_execution_rate_limit(
        "concurrent-user", now=100.0, max_attempts=2, window_seconds=10
    )
    assert allowed_first is True
    assert allowed_second is True
    assert blocked is False
    reset_execution_rate_limits()


def test_execution_rate_limit_window_expiry() -> None:
    reset_execution_rate_limits()
    first = check_execution_rate_limit(
        "expiry-user", now=100.0, max_attempts=1, window_seconds=1.0
    )
    blocked = check_execution_rate_limit(
        "expiry-user", now=100.5, max_attempts=1, window_seconds=1.0
    )
    allowed_after = check_execution_rate_limit(
        "expiry-user", now=101.1, max_attempts=1, window_seconds=1.0
    )
    assert first is True
    assert blocked is False
    assert allowed_after is True
    reset_execution_rate_limits()
