from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.excel_main_import_service import ExcelMainImportService  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        result = ExcelMainImportService.sync_main_dataset(
            db=db,
            actor="script:run_disease_screening_import",
        )
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
