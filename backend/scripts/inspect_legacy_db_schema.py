from __future__ import annotations

import json
import sys

from sqlalchemy import inspect


BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import engine  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    inspector = inspect(engine)
    payload: dict[str, list[str]] = {}
    for table_name in sorted(inspector.get_table_names()):
        payload[table_name] = [column["name"] for column in inspector.get_columns(table_name)]

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
