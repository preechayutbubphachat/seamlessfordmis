from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.profiling_service import ProfilingService  # noqa: E402
from app.services.source_sync_service import SourceSyncService  # noqa: E402


def main() -> None:
    paths = SourceSyncService.get_source_files()
    summary = ProfilingService.profile_disease_screening_files(paths)

    reports_dir = BACKEND_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "disease_screening_profile.json"
    markdown_path = reports_dir / "disease_screening_profile.md"

    json_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(ProfilingService.to_markdown(summary), encoding="utf-8")

    print(f"Wrote {json_path.name}")
    print(f"Wrote {markdown_path.name}")


if __name__ == "__main__":
    main()
