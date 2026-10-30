"""Tests for the Phase 1 health endpoint."""

from fastapi.testclient import TestClient

from stanford_ai_os.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "Stanford-AI OS"
