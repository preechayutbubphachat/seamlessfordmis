from __future__ import annotations

import json
import sys

from sqlalchemy import inspect


BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.models import *  # noqa: F403,F401,E402


TABLES_TO_COMPARE = [
    "import_jobs",
    "source_files",
    "disease_screening_records",
    "diagnosis_history",
    "patients",
    "target_group_jobs",
    "target_group_job_files",
    "target_group_sheets",
    "target_group_history_rows",
    "target_group_rows",
    "target_group_results",
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    output: dict[str, dict] = {}

    for table_name in TABLES_TO_COMPARE:
        model_table = Base.metadata.tables.get(table_name)
        model_columns = set(model_table.columns.keys()) if model_table is not None else set()
        legacy_columns = (
            {column["name"] for column in inspector.get_columns(table_name)}
            if table_name in existing_tables
            else set()
        )

        if table_name not in existing_tables:
            status = "missing_in_legacy"
        elif not model_columns:
            status = "missing_in_models"
        elif legacy_columns == model_columns:
            status = "compatible"
        elif legacy_columns & model_columns:
            status = "partially_compatible"
        else:
            status = "incompatible"

        output[table_name] = {
            "status": status,
            "legacy_columns": sorted(legacy_columns),
            "model_columns": sorted(model_columns),
            "shared_columns": sorted(legacy_columns & model_columns),
            "missing_in_legacy": sorted(model_columns - legacy_columns),
            "legacy_only": sorted(legacy_columns - model_columns),
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
