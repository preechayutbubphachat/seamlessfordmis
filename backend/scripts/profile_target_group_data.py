from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.profiling_service import ProfilingService  # noqa: E402
from app.utils.files import is_supported_source_file  # noqa: E402


def main() -> None:
    target_dir = REPO_ROOT / "data" / "targets"
    paths = sorted([path for path in target_dir.iterdir() if path.is_file() and is_supported_source_file(path)])
    summary = ProfilingService.profile_target_group_files(paths)

    reports_dir = BACKEND_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "target_group_profile.json"
    markdown_path = reports_dir / "target_group_profile.md"

    json_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(ProfilingService.to_markdown(summary), encoding="utf-8")

    print(f"Wrote {json_path.name}")
    print(f"Wrote {markdown_path.name}")


if __name__ == "__main__":
    main()
