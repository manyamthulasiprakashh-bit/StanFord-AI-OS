"""Tests for structured, privacy-safe application logging."""

import io
import json
import logging
import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from stanford_ai_os.main import app
from stanford_ai_os.observability.context import (
    get_request_id,
    reset_request_id,
    set_request_id,
)
from stanford_ai_os.observability.logging_config import (
    JsonFormatter,
    configure_logging,
    log_event,
)


def test_json_formatter_produces_valid_json_with_required_fields() -> None:
    logger = logging.getLogger("test.json.valid")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        log_event(logger, logging.INFO, "test_event", task_id="task-123", status_code=200)
        handler.flush()
        output = stream.getvalue().strip()
        data = json.loads(output)
        assert data["event"] == "test_event"
        assert data["level"] == "INFO"
        assert "timestamp" in data
        assert data["task_id"] == "task-123"
        assert data["status_code"] == 200
    finally:
        logger.removeHandler(handler)


def test_utc_timestamp_is_parseable() -> None:
    logger = logging.getLogger("test.json.timestamp")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        log_event(logger, logging.INFO, "timestamp_event")
        handler.flush()
        data = json.loads(stream.getvalue().strip())
        parsed = datetime.fromisoformat(data["timestamp"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == datetime.now(UTC).utcoffset()
    finally:
        logger.removeHandler(handler)


def test_configure_logging_uses_env_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STANFORD_AI_OS_LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG
    configure_logging("INFO")


def test_configure_logging_invalid_level_defaults_to_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STANFORD_AI_OS_LOG_LEVEL", "NOT_A_LEVEL")
    configure_logging()
    assert logging.getLogger().level == logging.INFO
    configure_logging("INFO")


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_path = tmp_path / "logging.db"
    os.environ["STANFORD_AI_OS_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["STANFORD_AI_OS_SECRET_KEY"] = "test-secret-key-at-least-32-characters"
    os.environ["STANFORD_AI_OS_ADMIN_PASSWORD"] = "test-admin-password"
    with TestClient(app) as test_client:
        yield test_client


def test_request_id_header_and_context(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    assert len(request_id) > 0
    # Context is reset after request.
    assert get_request_id() is None


def test_request_id_context_isolation() -> None:
    token = set_request_id("isolated-id")
    try:
        assert get_request_id() == "isolated-id"
    finally:
        reset_request_id(token)
    assert get_request_id() is None


def test_request_id_cleanup_after_exception() -> None:
    import uuid

    rid = str(uuid.uuid4())
    token = set_request_id(rid)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        pass
    finally:
        reset_request_id(token)
    assert get_request_id() is None


def test_sensitive_values_not_in_json_log() -> None:
    secret = "super-secret-value"
    logger = logging.getLogger("test.json.sensitive")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        # Attempt to pass a prohibited field; it should be dropped.
        log_event(logger, logging.INFO, "sensitive_event", task_id="task-1", password=secret)
        handler.flush()
        output = stream.getvalue()
        assert secret not in output
        data = json.loads(output.strip())
        assert "password" not in data
    finally:
        logger.removeHandler(handler)


def test_auth_events_present_and_safe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Trigger login failure and success.
    with caplog.at_level(logging.INFO):
        failed = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert failed.status_code == 401
        success = client.post(
            "/auth/login", json={"username": "admin", "password": "test-admin-password"}
        )
        assert success.status_code == 200

    assert "login_failed" in caplog.text
    assert "login_succeeded" in caplog.text
    assert "wrong" not in caplog.text
    assert success.json()["access_token"] not in caplog.text


def test_execution_events_and_rate_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from tests.test_task_execution import FakeProvider, FakeRouter

    login = client.post(
        "/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    token = login.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    task_resp = client.post("/tasks", json={"title": "Log task", "description": "details"})
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    provider = FakeProvider()
    monkeypatch.setattr(
        "stanford_ai_os.services.task_execution_service.get_model_router",
        lambda settings=None: FakeRouter(provider),
    )

    # Login token already in client? client fixture doesn't login. Use auth header.
    login = client.post(
        "/auth/login", json={"username": "admin", "password": "test-admin-password"}
    )
    token = login.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    with caplog.at_level(logging.INFO):
        first = client.post(f"/tasks/{task_id}/execute")
        assert first.status_code == 200

    assert "execution_started" in caplog.text
    assert "execution_succeeded" in caplog.text


def test_execution_rate_limited_event(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "rl.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("STANFORD_AI_OS_EXECUTION_RATE_LIMIT_ATTEMPTS", "1")
    monkeypatch.setenv("STANFORD_AI_OS_EXECUTION_RATE_LIMIT_WINDOW_SECONDS", "60")

    with TestClient(app) as c:
        login = c.post("/auth/login", json={"username": "admin", "password": "test-admin-password"})
        token = login.json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        task_resp = c.post("/tasks", json={"title": "RL task", "description": "details"})
        task_id = task_resp.json()["id"]

        from tests.test_task_execution import FakeProvider, FakeRouter

        provider = FakeProvider()
        monkeypatch.setattr(
            "stanford_ai_os.services.task_execution_service.get_model_router",
            lambda settings=None: FakeRouter(provider),
        )

        with caplog.at_level(logging.WARNING):
            first = c.post(f"/tasks/{task_id}/execute")
            assert first.status_code == 200
            second = c.post(f"/tasks/{task_id}/execute")
            assert second.status_code == 429

        assert "execution_rate_limited" in caplog.text
        assert len(provider.calls) == 1


def test_recovery_event_emitted(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "rec.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base, Task
    from stanford_ai_os.services import task_execution_history_service as history_service

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    task = Task(title="Recovery", description="Details")
    db.add(task)
    db.commit()
    db.refresh(task)
    execution = history_service.create_execution(db, task_id=task.id, status="running")
    db.close()

    with caplog.at_level(logging.INFO):
        db2 = Session()
        recovered = history_service.recover_execution(db2, execution.id)
        db2.close()

    assert recovered is not None
    assert recovered.status == "failure"
    assert "execution_recovered" in caplog.text
    engine.dispose()


def test_recovery_no_transition_not_reported(
    tmp_path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    db_path = tmp_path / "rec2.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base, Task
    from stanford_ai_os.services import task_execution_history_service as history_service

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    task = Task(title="Recovery2", description="Details")
    db.add(task)
    db.commit()
    db.refresh(task)
    execution = history_service.create_execution(db, task_id=task.id, status="running")
    # Mark terminal first
    history_service.update_execution(db, execution.id, status="success")
    db.close()

    caplog.clear()
    with caplog.at_level(logging.INFO):
        db2 = Session()
        result = history_service.recover_execution(db2, execution.id)
        db2.close()

    assert result is not None
    assert result.status == "success"
    assert "execution_recovered" not in caplog.text
    engine.dispose()


def test_handled_error_includes_request_id(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    response = client.get(f"/tasks/{__import__('uuid').uuid4()}")
    assert response.status_code == 404
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_unexpected_exception_returns_safe_500_with_request_id(client: TestClient) -> None:
    # Use the global app imported in main
    from stanford_ai_os.main import app as application

    @application.get("/__boom")
    def __boom():
        raise RuntimeError("secret boom details")

    try:
        response = client.get("/__boom")
        assert response.status_code == 500
        assert response.text == "Internal Server Error"
        assert "secret boom details" not in response.text
        rid = response.headers.get("X-Request-ID")
        assert rid is not None and len(rid) > 0
        # Context cleaned up
        from stanford_ai_os.observability.context import get_request_id

        assert get_request_id() is None
    finally:
        # Remove the temporary route
        application.routes[:] = [
            r for r in application.routes if getattr(r, "path", None) != "/__boom"
        ]


def test_request_id_matches_generated_value(client: TestClient) -> None:
    response = client.get("/health")
    rid = response.headers.get("X-Request-ID")
    assert rid is not None
    # Validate UUID format
    import uuid

    uuid.UUID(rid)
