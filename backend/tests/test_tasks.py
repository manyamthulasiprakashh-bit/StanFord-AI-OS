"""Tests for the Phase 2 task management API."""

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stanford_ai_os.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "tasks.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    with TestClient(app) as test_client:
        yield test_client


def test_create_task(client: TestClient) -> None:
    response = client.post(
        "/tasks",
        json={"title": "Write Phase 2 tests", "description": "Cover CRUD basics"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Write Phase 2 tests"
    assert data["description"] == "Cover CRUD basics"
    assert data["status"] == "pending"
    uuid.UUID(data["id"])
    assert data["created_at"]
    assert data["updated_at"]


def test_list_tasks(client: TestClient) -> None:
    client.post("/tasks", json={"title": "First"})
    client.post("/tasks", json={"title": "Second"})

    response = client.get("/tasks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    titles = {task["title"] for task in data}
    assert titles == {"First", "Second"}


def test_get_task_by_id(client: TestClient) -> None:
    created = client.post("/tasks", json={"title": "Retrieve me"}).json()

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["title"] == "Retrieve me"


def test_get_missing_task_returns_404(client: TestClient) -> None:
    response = client.get(f"/tasks/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_empty_title_is_rejected(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": ""})

    assert response.status_code == 422


def test_task_persists_across_connections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "persist.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")

    with TestClient(app) as first_client:
        created = first_client.post("/tasks", json={"title": "Persistent task"})
        assert created.status_code == 201

    with TestClient(app) as second_client:
        response = second_client.get("/tasks")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["title"] == "Persistent task"
