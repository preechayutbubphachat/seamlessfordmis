"""Database dialect compatibility helpers.

Thin abstractions that paper over differences between PostgreSQL and SQLite
without changing any business-logic semantics.

Rules:
- PostgreSQL callers never break.  All helpers default to PostgreSQL behaviour
  when the effective dialect is anything other than "sqlite".
- No business logic lives here.
- No raw string SQL is constructed here.  Always use the SQLAlchemy Core API.
- Helpers NOT yet ported for SQLite raise NotImplementedError on SQLite so
  failures are loud and traceable rather than silently broken.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement


# ---------------------------------------------------------------------------
# Engine dialect helpers
# ---------------------------------------------------------------------------


def database_dialect_name(engine: Engine) -> str:
    return engine.dialect.name


def is_sqlite_engine(engine: Engine) -> bool:
    return database_dialect_name(engine) == "sqlite"


def is_postgres_engine(engine: Engine) -> bool:
    return database_dialect_name(engine) == "postgresql"


# ---------------------------------------------------------------------------
# Session dialect helpers
# ---------------------------------------------------------------------------


def _session_dialect_name(db: Session) -> str:
    """Return the dialect name for a session.

    Priority:
    1. ``settings.is_sqlite`` - authoritative in production.
    2. ``db.get_bind().dialect.name`` - reliable in tests with explicit engine.
    3. Falls back to ``"postgresql"`` as safe default.
    """
    try:
        from app.config import settings as _settings  # noqa: PLC0415
        if _settings.is_sqlite:
            return "sqlite"
        # settings says postgres, but double-check the actual engine in case
        # we are in a test with an explicit SQLite engine and env vars not set.
        try:
            bind = db.get_bind()
            if bind is not None and bind.dialect.name == "sqlite":
                return "sqlite"
        except Exception:  # noqa: BLE001
            pass
        return _settings.effective_database_engine
    except Exception:  # noqa: BLE001
        try:
            bind = db.get_bind()
            if bind is not None:
                return bind.dialect.name
        except Exception:  # noqa: BLE001
            pass
        return "postgresql"


def is_sqlite_session(db: Session) -> bool:
    return _session_dialect_name(db) == "sqlite"


# ---------------------------------------------------------------------------
# Case-insensitive search (portable)
# ---------------------------------------------------------------------------


def case_insensitive_contains(column: ColumnElement[str], value: str) -> ColumnElement[bool]:
    """Portable ILIKE / case-insensitive LIKE.

    SQLAlchemy's ``.ilike()`` is safe on SQLite (compiles to
    ``LOWER(col) LIKE LOWER(:param)``), but this helper is available for
    places that need a bare ColumnElement.
    """
    pattern = f"%{value.lower()}%"
    return func.lower(column).like(pattern)


# ---------------------------------------------------------------------------
# Dialect-aware upsert (INSERT ... ON CONFLICT DO UPDATE)
# ---------------------------------------------------------------------------


def make_upsert_stmt(
    db: Session,
    model_class: Any,
    values: dict[str, Any],
    index_elements: list[str],
    set_: dict[str, Any],
):
    """Build a dialect-aware INSERT ... ON CONFLICT DO UPDATE statement.

    Both the PostgreSQL and SQLite dialects expose an identical API in
    SQLAlchemy 2.x::

        insert().values(...).on_conflict_do_update(
            index_elements=[...], set_={...}
        )

    We dispatch to the correct dialect-specific ``insert`` constructor so
    the compiled SQL is syntactically valid on the target database.

    Supported dialects: PostgreSQL, SQLite (>= 3.24.0 / Python >= 3.8).
    The PostgreSQL path is used as the safe default for any unrecognised
    dialect.
    """
    if is_sqlite_session(db):
        from sqlalchemy.dialects.sqlite import insert as _sqlite_insert  # noqa: PLC0415
        return (
            _sqlite_insert(model_class)
            .values(**values)
            .on_conflict_do_update(index_elements=index_elements, set_=set_)
        )
    else:
        from sqlalchemy.dialects.postgresql import insert as _pg_insert  # noqa: PLC0415
        return (
            _pg_insert(model_class)
            .values(**values)
            .on_conflict_do_update(index_elements=index_elements, set_=set_)
        )


# ---------------------------------------------------------------------------
# Phase F raw SQL guard
# ---------------------------------------------------------------------------


def raise_if_sqlite_unsupported(db: Session, feature_name: str) -> None:
    """Raise NotImplementedError if the session is SQLite and the named
    feature has not been ported.

    Call this at the top of any service method that still uses
    PostgreSQL-specific raw SQL that has not been made dialect-aware yet.
    This makes failures loud and traceable instead of silently executing
    broken SQL on SQLite.

    Example::

        # Inside PhaseFPopulationService._step_person_master:
        raise_if_sqlite_unsupported(db, "PhaseFPopulationService._step_person_master")
    """
    if is_sqlite_session(db):
        raise NotImplementedError(
            f"{feature_name!r} contains PostgreSQL-specific raw SQL that has "
            "not been ported to SQLite yet. "
            "Tracked in docs/DESKTOP_SQLITE_D3_WORKFLOW_NOTES.md. "
            "Do not call this service in desktop_local mode until it is ported."
        )
