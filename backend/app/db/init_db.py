from app.db.base import Base
from app.db.session import engine
from app.models import *  # noqa: F403,F401
from app.config import settings


def _ensure_sqlite_columns() -> None:
    """Add nullable columns introduced after a desktop DB was first created.

    create_all() never ALTERs existing tables, so desktop SQLite databases that
    predate a new column need a lightweight, idempotent ADD COLUMN. Only additive
    nullable columns — no data loss, safe to run on every startup. (LAN/Postgres
    uses Alembic migrations instead.)
    """
    from sqlalchemy import text

    additive_columns = {
        "target_group_result_summaries": [
            ("normalization_version", "INTEGER"),
        ],
    }
    with engine.begin() as connection:
        for table, columns in additive_columns.items():
            existing = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
            }
            if not existing:
                continue  # table not created yet — create_all will include the column
            for column_name, column_type in columns:
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"))


def _init_desktop_metadata() -> None:
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS desktop_schema_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO desktop_schema_metadata (key, value)
                VALUES ('schema_strategy', 'create_all_prototype')
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """
            )
        )


def init_db() -> None:
    if settings.is_desktop_local and settings.is_sqlite:
        from app.desktop.paths import init_desktop_paths

        init_desktop_paths()
    Base.metadata.create_all(bind=engine)
    if settings.is_desktop_local and settings.is_sqlite:
        _ensure_sqlite_columns()
        _init_desktop_metadata()
        # Desktop SQLite ships an empty DB; the disease/service catalog
        # (disease_mapping) must be seeded or the "สร้างผลลัพธ์" page has no
        # options. Idempotent — only seeds when the table is empty, never wipes.
        from app.seeds.disease_mapping_seed import seed_disease_mapping_if_empty

        seed_disease_mapping_if_empty()


if __name__ == "__main__":
    init_db()
