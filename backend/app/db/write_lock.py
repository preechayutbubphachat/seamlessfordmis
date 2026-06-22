"""Application-level single-writer guard for Desktop Local Edition (SQLite).

SQLite allows only one writer at a time. When two mutating requests (e.g. a
double-clicked upload, or upload + generate) overlap, the second hits
``database is locked``. PostgreSQL (LAN edition) handles concurrent writers with
MVCC and needs none of this — the guard is a no-op there.

Usage (wrap the mutating call at the endpoint layer, NOT inside business logic)::

    from app.db.write_lock import sqlite_write_lock

    with sqlite_write_lock():
        return SomeService.do_write(db, ...)

Behaviour:
- SQLite engine  → serialize writers through a process-wide re-entrant lock.
  A waiting request blocks up to ``ACQUIRE_TIMEOUT_SEC``; if it still cannot
  acquire, ``WriteBusyError`` is raised (mapped to HTTP 423 with a friendly
  Thai message). This prevents duplicate jobs from rapid double-submits.
- PostgreSQL engine → no-op (yields immediately).

The lock only serializes writers; it never bypasses transaction/commit logic,
so import/matching/result-generation business rules are unchanged.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

from app.config import settings


class WriteBusyError(Exception):
    """Raised when the desktop SQLite single-writer lock cannot be acquired in time."""

    def __init__(
        self,
        message: str = (
            "มีงานนำเข้า/บันทึกข้อมูลกำลังทำงานอยู่ กรุณารอให้เสร็จก่อนแล้วลองใหม่อีกครั้ง"
        ),
    ) -> None:
        self.message = message
        super().__init__(message)


# Process-wide re-entrant lock. FastAPI runs sync endpoints in a threadpool, so a
# threading lock (not asyncio) is the correct primitive. RLock keeps a single
# thread from deadlocking itself if write paths ever nest.
_write_lock = threading.RLock()

# Max time a waiting writer blocks for the lock before returning a busy error.
ACQUIRE_TIMEOUT_SEC = 30.0


def _serialize_writes() -> bool:
    # Only SQLite (Desktop Local) needs application-level single-writer behaviour.
    return settings.is_sqlite


@contextmanager
def sqlite_write_lock():
    """Serialize SQLite writers; no-op on PostgreSQL."""
    if not _serialize_writes():
        yield
        return

    acquired = _write_lock.acquire(timeout=ACQUIRE_TIMEOUT_SEC)
    if not acquired:
        raise WriteBusyError()
    try:
        yield
    finally:
        _write_lock.release()
