from __future__ import annotations

from app.config import settings
from app.db.init_db import init_db


def init_desktop_db() -> None:
    if not settings.is_desktop_local or not settings.is_sqlite:
        raise RuntimeError("Desktop SQLite bootstrap requires APP_EDITION=desktop_local and DATABASE_ENGINE=sqlite")

    init_db()


if __name__ == "__main__":
    init_desktop_db()
    print("Desktop SQLite prototype schema initialized.")
