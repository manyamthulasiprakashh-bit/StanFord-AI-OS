"""Database engine and session helpers."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from stanford_ai_os.config import get_settings
from stanford_ai_os.db.models import Base


def _connect_args(database_url: str) -> dict[str, Any]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _create_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine for the given database URL."""

    engine = create_engine(
        database_url,
        connect_args=_connect_args(database_url),
        future=True,
    )

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_engine() -> Engine:
    """Create a fresh SQLAlchemy engine from the configured database URL.

    This remains available for direct callers and tests that manage their own
    engine lifecycle.
    """

    settings = get_settings()
    return _create_engine(settings.database_url)


# Shared, application-scoped engine cache keyed by database URL. Engines are
# retained for reuse and disposed only through explicit lifecycle calls.
_shared_engines: dict[str, Engine] = {}


def get_shared_engine() -> Engine:
    """Return a shared engine for the currently configured database URL.

    A new engine is created when a previously unseen URL is used. Engines are
    not disposed automatically when the URL changes; explicit disposal is
    required to avoid interrupting active sessions.
    """

    settings = get_settings()
    database_url = settings.database_url
    engine = _shared_engines.get(database_url)
    if engine is None:
        engine = _create_engine(database_url)
        _shared_engines[database_url] = engine
    return engine


def dispose_shared_engine() -> None:
    """Dispose all shared engines and clear the cache."""

    for engine in list(_shared_engines.values()):
        engine.dispose()
    _shared_engines.clear()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure tables exist.

    Tables are created with ``checkfirst=True`` (SQLAlchemy default), so existing
    data is never deleted during startup or request handling.
    """

    engine = get_shared_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def reset_shared_engines() -> None:
    """Clear the shared engine cache without disposing.

    Intended for tests that need to drop cached engines between cases.
    """

    _shared_engines.clear()
