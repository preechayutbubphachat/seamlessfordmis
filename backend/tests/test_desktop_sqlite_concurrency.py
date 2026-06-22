"""Desktop Local Edition — SQLite concurrency / "database is locked" guards.

Covers the D4.7.2 fix round:
  C1  SQLite engine sets busy_timeout (waits instead of failing on lock)
  C2  sqlite_write_lock serializes writers; raises WriteBusyError when busy
  C3  write lock is a no-op when not SQLite (PostgreSQL / LAN edition)
  C4  app registers friendly handlers for WriteBusyError + OperationalError
  C5  WriteBusyError -> HTTP 423 with a friendly (non-SQL) message
  C6  OperationalError "database is locked" -> HTTP 503 friendly, no raw SQL

All synthetic — no DB data, no patient identifiers. Run with:
    cd backend && pytest tests/test_desktop_sqlite_concurrency.py -v
"""

from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.db import session as session_module
from app.db import write_lock as write_lock_module
from app.db.write_lock import WriteBusyError, sqlite_write_lock
from app.main import app


# ---------------------------------------------------------------------------
# C1 — busy_timeout PRAGMA
# ---------------------------------------------------------------------------
def test_sqlite_busy_timeout_pragma_is_set(tmp_path):
    db_file = tmp_path / "busy.db"
    engine = create_engine(f"sqlite:///{db_file}", future=True, connect_args={"check_same_thread": False})
    session_module._configure_sqlite_pragmas(engine)
    with engine.connect() as conn:
        busy = conn.execute(text("PRAGMA busy_timeout")).scalar()
        journal = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert busy == session_module.SQLITE_BUSY_TIMEOUT_MS
    assert str(journal).lower() == "wal"


# ---------------------------------------------------------------------------
# C2 / C3 — write lock behaviour
# ---------------------------------------------------------------------------
def test_write_lock_raises_when_busy(monkeypatch):
    # Force SQLite serialization mode and a short acquire timeout (fast test).
    monkeypatch.setattr(write_lock_module, "_serialize_writes", lambda: True)
    monkeypatch.setattr(write_lock_module, "ACQUIRE_TIMEOUT_SEC", 0.2)

    held = threading.Event()
    release = threading.Event()

    def hold_lock():
        with sqlite_write_lock():
            held.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=hold_lock)
    worker.start()
    try:
        assert held.wait(timeout=5), "background thread never acquired the lock"
        # Lock is held by the worker thread -> a second writer must give up.
        with pytest.raises(WriteBusyError):
            with sqlite_write_lock():
                pass
    finally:
        release.set()
        worker.join(timeout=5)

    # Once released, the lock is acquirable again (no leak).
    with sqlite_write_lock():
        pass


def test_write_lock_noop_when_not_sqlite(monkeypatch):
    monkeypatch.setattr(write_lock_module, "_serialize_writes", lambda: False)
    # Even if the lock is held elsewhere, non-sqlite must not block/raise.
    write_lock_module._write_lock.acquire()
    try:
        with sqlite_write_lock():
            pass  # reached => no-op path
    finally:
        write_lock_module._write_lock.release()


# ---------------------------------------------------------------------------
# C4 — handlers registered
# ---------------------------------------------------------------------------
def test_friendly_handlers_registered():
    assert WriteBusyError in app.exception_handlers
    assert OperationalError in app.exception_handlers


# ---------------------------------------------------------------------------
# C5 / C6 — handlers produce friendly responses, no raw SQL leak
# ---------------------------------------------------------------------------
def _client_with_probe_routes() -> TestClient:
    @app.get("/__test__/write-busy")
    def _raise_busy():  # noqa: ANN202
        raise WriteBusyError()

    @app.get("/__test__/db-locked")
    def _raise_locked():  # noqa: ANN202
        raise OperationalError(
            "INSERT INTO target_group_jobs (id, group_name) VALUES (?, ?)",
            {},
            Exception("database is locked"),
        )

    return TestClient(app, raise_server_exceptions=False)


def test_write_busy_maps_to_423():
    client = _client_with_probe_routes()
    resp = client.get("/__test__/write-busy")
    assert resp.status_code == 423
    body = resp.json()
    assert body["error_type"] == "WriteBusyError"
    assert "รอ" in body["detail"]  # friendly Thai message
    assert "INSERT" not in body["detail"]


def test_db_locked_maps_to_503_without_sql():
    client = _client_with_probe_routes()
    resp = client.get("/__test__/db-locked")
    assert resp.status_code == 503
    body = resp.json()
    assert body["error_type"] == "DatabaseLocked"
    assert "ฐานข้อมูล" in body["detail"]
    # Raw SQL / table name must never reach the client.
    assert "INSERT" not in body["detail"]
    assert "target_group_jobs" not in body["detail"]
