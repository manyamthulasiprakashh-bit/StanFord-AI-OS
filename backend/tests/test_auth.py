"""Tests for the initial authentication foundation."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from stanford_ai_os.config import get_settings
from stanford_ai_os.main import app


@pytest.fixture
def unauthenticated_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")
    with TestClient(app) as test_client:
        yield test_client


def test_health_is_public(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/health")

    assert response.status_code == 200


def test_login_success_returns_bearer_token(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert data["access_token"]


def test_login_invalid_username_returns_generic_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "unknown", "password": "test-admin-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_invalid_password_returns_generic_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_missing_token_rejects_protected_endpoint(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get("/tasks")

    assert response.status_code == 401


def test_malformed_token_rejects_protected_endpoint(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get(
        "/tasks", headers={"Authorization": "Bearer not-a-token"}
    )

    assert response.status_code == 401


def test_expired_token_rejects_protected_endpoint(
    unauthenticated_client: TestClient,
) -> None:
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": "admin",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        settings.secret_key,
        algorithm="HS256",
    )

    response = unauthenticated_client.get(
        "/tasks", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


def test_authenticated_user_can_access_protected_endpoints(
    unauthenticated_client: TestClient,
) -> None:
    login_response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    task_response = unauthenticated_client.post(
        "/tasks", json={"title": "Authenticated task"}, headers=headers
    )
    assert task_response.status_code == 201

    list_response = unauthenticated_client.get("/tasks", headers=headers)
    assert list_response.status_code == 200

    me_response = unauthenticated_client.get("/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"
    assert "password_hash" not in me_response.json()


def test_read_current_user_does_not_expose_password_hash(
    unauthenticated_client: TestClient,
) -> None:
    login_response = unauthenticated_client.post(
        "/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    token = login_response.json()["access_token"]

    response = unauthenticated_client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert "password_hash" not in response.text


def test_inactive_user_cannot_access_protected_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "inactive.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")

    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine
    from stanford_ai_os.services.auth_service import (
        bootstrap_admin_user,
        create_access_token,
        get_settings,
    )

    engine = get_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = sessionmaker(bind=engine)()
    try:
        user = bootstrap_admin_user(db, get_settings())
        assert user is not None
        token = create_access_token(user.username)
        user.is_active = False
        db.commit()
    finally:
        db.close()
        engine.dispose()

    with TestClient(app) as client:
        response = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_missing_secret_configuration_returns_safe_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "missing-secret.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.delenv("STANFORD_AI_OS_SECRET_KEY", raising=False)

    with TestClient(app) as client:
        login_response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        protected_response = client.get(
            "/tasks", headers={"Authorization": "Bearer not-a-token"}
        )

    assert login_response.status_code == 503
    assert protected_response.status_code == 503


def test_wrong_secret_token_is_rejected(
    unauthenticated_client: TestClient,
) -> None:
    wrong_secret_token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "wrong-secret-key-at-least-32-characters",
        algorithm="HS256",
    )

    response = unauthenticated_client.get(
        "/tasks", headers={"Authorization": f"Bearer {wrong_secret_token}"}
    )

    assert response.status_code == 401


def test_token_with_unexpected_algorithm_is_rejected(
    unauthenticated_client: TestClient,
) -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm="HS256",
    )
    # Tamper with the algorithm portion of the JWT header.
    header, payload, signature = token.split(".")
    tampered = f"{header[:-1]}X.{payload}.{signature}"

    response = unauthenticated_client.get(
        "/tasks", headers={"Authorization": f"Bearer {tampered}"}
    )

    assert response.status_code == 401


def test_token_missing_subject_is_rejected(
    unauthenticated_client: TestClient,
) -> None:
    settings = get_settings()
    token = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm="HS256",
    )

    response = unauthenticated_client.get(
        "/tasks", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_tampered_token_is_rejected(unauthenticated_client: TestClient) -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm="HS256",
    )
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    response = unauthenticated_client.get(
        "/tasks", headers={"Authorization": f"Bearer {tampered}"}
    )

    assert response.status_code == 401


def test_auth_me_requires_token(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/auth/me")

    assert response.status_code == 401


def test_admin_bootstrap_existing_user_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "bootstrap.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")

    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine
    from stanford_ai_os.services.auth_service import (
        bootstrap_admin_user,
        get_settings,
    )

    engine = get_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = sessionmaker(bind=engine)()
    try:
        first = bootstrap_admin_user(db, get_settings())
        assert first is not None
        original_hash = first.password_hash
        first_id = first.id

        second = bootstrap_admin_user(db, get_settings())
        assert second is not None
        assert second.id == first_id
        assert second.password_hash == original_hash
    finally:
        db.close()
        engine.dispose()


def test_admin_bootstrap_without_password_returns_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "no-password.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.delenv("STANFORD_AI_OS_ADMIN_PASSWORD", raising=False)

    from sqlalchemy.orm import sessionmaker

    from stanford_ai_os.db.models import Base
    from stanford_ai_os.db.session import get_engine
    from stanford_ai_os.services.auth_service import (
        bootstrap_admin_user,
        get_settings,
    )

    engine = get_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = sessionmaker(bind=engine)()
    try:
        assert bootstrap_admin_user(db, get_settings()) is None
    finally:
        db.close()
        engine.dispose()


def test_argon2_malformed_hash_fails_safely() -> None:
    from stanford_ai_os.services.auth_service import verify_password

    assert verify_password("password", "not-an-argon2-hash") is False


def test_login_rate_limit_returns_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "rate-limit.db"
    monkeypatch.setenv("STANFORD_AI_OS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STANFORD_AI_OS_SECRET_KEY", "test-secret-key-at-least-32-characters")
    monkeypatch.setenv("STANFORD_AI_OS_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("STANFORD_AI_OS_LOGIN_RATE_LIMIT_ATTEMPTS", "2")
    monkeypatch.setenv("STANFORD_AI_OS_LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60")

    with TestClient(app) as client:
        first = client.post(
            "/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        second = client.post(
            "/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )
        third = client.post(
            "/auth/login",
            json={"username": "admin", "password": "test-admin-password"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["detail"] == "Too many login attempts"


def test_audit_logs_do_not_include_sensitive_values(
    unauthenticated_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    password = "test-admin-password"
    with caplog.at_level("INFO"):
        success = unauthenticated_client.post(
            "/auth/login",
            json={"username": "admin", "password": password},
        )
        token = success.json()["access_token"]
        unauthenticated_client.get(
            "/tasks", headers={"Authorization": f"Bearer {token}"}
        )
        unauthenticated_client.get(
            "/tasks", headers={"Authorization": "Bearer not-a-token"}
        )

    assert "login_succeeded" in caplog.text
    assert "invalid_access_token" in caplog.text
    assert password not in caplog.text
    assert token not in caplog.text
