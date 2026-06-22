from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi import UploadFile


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.target_group_import_service import TargetGroupImportService  # noqa: E402


def _default_target_files() -> list[Path]:
    candidates = [
        REPO_ROOT / "data" / "targets" / "หญิงไทยอายุ 30 - 60 ปี ได้รับการตรวจคัดกรองมะเ.XLS",
        REPO_ROOT / "data" / "samples" / "sample_target_group.xlsx",
        REPO_ROOT / "data" / "samples" / "live_target_group.xlsx",
    ]
    return [path for path in candidates if path.exists()]


def _build_upload_file(path: Path) -> UploadFile:
    return UploadFile(filename=path.name, file=path.open("rb"))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run Phase 3 target group import against local files")
    parser.add_argument("--group-name", default="กลุ่มเป้าหมายทดสอบจากสคริปต์")
    parser.add_argument("files", nargs="*", help="Optional file paths to import")
    args = parser.parse_args()

    file_paths = [Path(item).resolve() for item in args.files] if args.files else _default_target_files()
    if not file_paths:
        raise SystemExit("No target group files found. Pass file paths explicitly.")

    upload_files = [_build_upload_file(path) for path in file_paths]
    try:
        with SessionLocal() as db:
            response = TargetGroupImportService.upload_files(
                db=db,
                group_name=args.group_name,
                upload_files=upload_files,
                actor="script:run_target_group_import",
            )
            print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))
    finally:
        for upload_file in upload_files:
            upload_file.file.close()


if __name__ == "__main__":
    main()
