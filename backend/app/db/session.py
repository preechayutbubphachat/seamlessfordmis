from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _sqlite_path_from_url(database_url: str) -> Path | None:
    url = make_url(database_url)
    if url.drivername not in {"sqlite", "sqlite+pysqlite"}:
        return None
    if not url.database or url.database == ":memory:":
        return None
    return Path(url.database)


# How long SQLite waits for a held write lock before giving up. Without this,
# a contended write fails INSTANTLY with "database is locked" (the D4 blocker).
# Set both at the DBAPI level (connect_args timeout, seconds) and via PRAGMA
# busy_timeout (milliseconds) so the value survives across pooled connections.
SQLITE_BUSY_TIMEOUT_MS = 30_000


def _configure_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ANN001, ARG001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Wait (not fail) when another connection holds the write lock.
            cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()


def _create_engine() -> Engine:
    if settings.is_sqlite:
        sqlite_path = _sqlite_path_from_url(settings.database_url)
        if sqlite_path is not None:
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        sqlite_engine = create_engine(
            settings.database_url,
            future=True,
            # timeout (seconds) = how long the sqlite3 driver blocks waiting for
            # a lock before raising OperationalError. Mirrors busy_timeout.
            connect_args={"check_same_thread": False, "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000},
        )
        _configure_sqlite_pragmas(sqlite_engine)
        return sqlite_engine

    # PostgreSQL / LAN edition — unchanged (MVCC handles concurrent writers).
    return create_engine(settings.database_url, future=True, pool_pre_ping=True)


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
