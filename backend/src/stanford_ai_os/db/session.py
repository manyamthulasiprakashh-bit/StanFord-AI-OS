"""Database engine and session helpers."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from stanford_ai_os.config import get_settings
from stanford_ai_os.db.models import Base


def _connect_args(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def get_engine():
    """Create a SQLAlchemy engine from the configured database URL."""

    settings = get_settings()
    engine = create_engine(
        settings.database_url,
        connect_args=_connect_args(settings.database_url),
        future=True,
    )

    if settings.database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure tables exist.

    Tables are created with ``checkfirst=True`` (SQLAlchemy default), so existing
    data is never deleted during startup or request handling.
    """

    engine = get_engine()
    Base.metadata.create_all(bind=engine, checkfirst=True)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()
