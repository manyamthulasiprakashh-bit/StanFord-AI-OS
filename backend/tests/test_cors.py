"""Tests for backend CORS configuration."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from stanford_ai_os.main import configure_cors, parse_cors_allowed_origins


def test_parse_cors_allowed_origins_trims_and_ignores_empty() -> None:
    assert parse_cors_allowed_origins("") == []
    assert parse_cors_allowed_origins("  ") == []
    assert parse_cors_allowed_origins("http://a.example, http://b.example") == [
        "http://a.example",
        "http://b.example",
    ]
    assert parse_cors_allowed_origins("http://a.example,,http://b.example") == [
        "http://a.example",
        "http://b.example",
    ]


def test_configure_cors_adds_middleware_for_origins() -> None:
    app = FastAPI()
    configure_cors(app, ["http://allowed.example"])
    assert any("CORSMiddleware" in m.cls.__name__ for m in app.user_middleware)


def test_configure_cors_does_nothing_without_origins() -> None:
    app = FastAPI()
    configure_cors(app, [])
    assert not any("CORSMiddleware" in m.cls.__name__ for m in app.user_middleware)


def test_cors_preflight_allowed_origin() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    configure_cors(app, ["http://allowed.example"])
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://allowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://allowed.example"


def test_cors_preflight_disallowed_origin() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    configure_cors(app, ["http://allowed.example"])
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://disallowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_credentials_not_enabled() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    configure_cors(app, ["http://allowed.example"])
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://allowed.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers.get("access-control-allow-credentials") != "true"
