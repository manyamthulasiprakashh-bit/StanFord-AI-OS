"""Tests for the task execution history API."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tests.test_task_execution import FakeProvider, FakeRouter

from stanford_ai_os.db.models import Base, TaskExecution
from stanford_ai_os.main import app


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "history_api.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{path}")
    return path


@pytest.fixture
def client(db_path: Path) -> TestClient:
    with TestClient(app) as test_client:
        login_response = test_client.post(
            "/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client


def _create_task(client: TestClient, title: str = "History API task") -> dict[str, Any]:
    response = client.post("/tasks", json={"title": title, "description": "Details"})
    assert response.status_code == 201
    return response.json()


def _insert_executions(db_path: Path, task_id: str, specs: list[dict[str, Any]]) -> list[str]:
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    ids: list[str] = []
    try:
        for spec in specs:
            execution = TaskExecution(
                task_id=task_id,
                status=spec.get("status", "success"),
                provider=spec.get("provider", "fake"),
                model=spec.get("model", "fake-model"),
                duration_ms=spec.get("duration_ms", 1),
                error_category=spec.get("error_category"),
                created_at=spec["created_at"],
                started_at=spec.get("started_at", spec["created_at"]),
                completed_at=spec.get("completed_at", spec["created_at"]),
            )
            db.add(execution)
            db.flush()
            ids.append(execution.id)
        db.commit()
    finally:
        db.close()
        engine.dispose()
    return ids


def test_list_history_for_missing_task_returns_404(client: TestClient) -> None:
    response = client.get(f"/tasks/{uuid.uuid4()}/executions")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_list_history_for_task_without_executions_returns_empty_array(
    client: TestClient,
) -> None:
    created = _create_task(client)

    response = client.get(f"/tasks/{created['id']}/executions")

    assert response.status_code == 200
    assert response.json() == []


def test_list_history_returns_correct_metadata(client: TestClient, db_path: Path) -> None:
    created = _create_task(client)
    now = datetime.now(UTC)
    _insert_executions(
        db_path,
        created["id"],
        [
            {
                "status": "success",
                "provider": "nvidia",
                "model": "meta/llama-3.3-70b-instruct",
                "duration_ms": 42,
                "error_category": None,
                "created_at": now,
            }
        ],
    )

    response = client.get(f"/tasks/{created['id']}/executions")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    record = data[0]
    assert record["task_id"] == created["id"]
    assert record["status"] == "success"
    assert record["provider"] == "nvidia"
    assert record["model"] == "meta/llama-3.3-70b-instruct"
    assert record["duration_ms"] == 42
    assert record["error_category"] is None


def test_list_history_ordering_uses_created_at_then_id(
    client: TestClient, db_path: Path
) -> None:
    created = _create_task(client)
    same_time = datetime.now(UTC)
    ids = _insert_executions(
        db_path,
        created["id"],
        [
            {"status": "success", "created_at": same_time},
            {"status": "failure", "created_at": same_time},
        ],
    )

    response = client.get(f"/tasks/{created['id']}/executions")

    assert response.status_code == 200
    data = response.json()
    assert [record["id"] for record in data] == sorted(ids, reverse=True)


def test_list_history_default_limit_is_20(client: TestClient, db_path: Path) -> None:
    created = _create_task(client)
    now = datetime.now(UTC)
    _insert_executions(
        db_path,
        created["id"],
        [{"status": "success", "created_at": now - timedelta(seconds=i)} for i in range(25)],
    )

    response = client.get(f"/tasks/{created['id']}/executions")

    assert response.status_code == 200
    assert len(response.json()) == 20


def test_list_history_accepts_limit_100(client: TestClient, db_path: Path) -> None:
    created = _create_task(client)
    now = datetime.now(UTC)
    _insert_executions(
        db_path,
        created["id"],
        [{"status": "success", "created_at": now - timedelta(seconds=i)} for i in range(25)],
    )

    response = client.get(f"/tasks/{created['id']}/executions?limit=100")

    assert response.status_code == 200
    assert len(response.json()) == 25


def test_list_history_rejects_limit_below_one(client: TestClient) -> None:
    created = _create_task(client)

    response = client.get(f"/tasks/{created['id']}/executions?limit=0")

    assert response.status_code == 422


def test_list_history_rejects_limit_above_100(client: TestClient) -> None:
    created = _create_task(client)

    response = client.get(f"/tasks/{created['id']}/executions?limit=101")

    assert response.status_code == 422


def test_list_history_rejects_negative_offset(client: TestClient) -> None:
    created = _create_task(client)

    response = client.get(f"/tasks/{created['id']}/executions?offset=-1")

    assert response.status_code == 422


def test_list_history_pagination_returns_expected_subset(
    client: TestClient, db_path: Path
) -> None:
    created = _create_task(client)
    now = datetime.now(UTC)
    ids = _insert_executions(
        db_path,
        created["id"],
        [{"status": "success", "created_at": now - timedelta(seconds=i)} for i in range(5)],
    )

    response = client.get(f"/tasks/{created['id']}/executions?limit=2&offset=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert [record["id"] for record in data] == ids[1:3]


def test_get_existing_execution_returns_200(client: TestClient, db_path: Path) -> None:
    created = _create_task(client)
    now = datetime.now(UTC)
    ids = _insert_executions(
        db_path,
        created["id"],
        [{"status": "success", "created_at": now}],
    )

    response = client.get(f"/executions/{ids[0]}")

    assert response.status_code == 200
    assert response.json()["id"] == ids[0]
    assert response.json()["task_id"] == created["id"]


def test_get_unknown_execution_returns_404(client: TestClient) -> None:
    response = client.get(f"/executions/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Execution not found"


def test_history_response_contains_only_approved_fields(
    client: TestClient, db_path: Path
) -> None:
    created = _create_task(client)
    now = datetime.now(UTC)
    _insert_executions(
        db_path,
        created["id"],
        [{"status": "success", "created_at": now}],
    )

    response = client.get(f"/tasks/{created['id']}/executions")

    assert response.status_code == 200
    record = response.json()[0]
    assert set(record) == {
        "id",
        "task_id",
        "status",
        "provider",
        "model",
        "duration_ms",
        "error_category",
        "created_at",
        "started_at",
        "completed_at",
    }


def test_existing_task_and_execution_endpoints_remain_compatible(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = _create_task(client, "Compatibility task")
    listed = client.get("/tasks")
    retrieved = client.get(f"/tasks/{created['id']}")

    assert listed.status_code == 200
    assert any(task["id"] == created["id"] for task in listed.json())
    assert retrieved.status_code == 200

    provider = FakeProvider()
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )
    execution_response = client.post(f"/tasks/{created['id']}/execute")

    assert execution_response.status_code == 200
    assert execution_response.json()["output"] == "Generated result"
