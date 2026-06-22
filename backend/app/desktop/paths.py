from __future__ import annotations

import json
from pathlib import Path

from app.config import settings


def desktop_paths() -> dict[str, Path]:
    data_dir = settings.resolve_local_path(settings.data_dir)
    return {
        "data_dir": data_dir,
        "database_file": data_dir / "seamlessfordmis.db",
        "uploads_dir": settings.resolve_local_path(settings.upload_dir),
        "source_files_dir": settings.resolve_local_path(settings.source_data_dir),
        "reports_dir": settings.resolve_local_path(settings.reports_dir),
        "exports_dir": settings.resolve_local_path(settings.exports_dir),
        "backups_dir": settings.resolve_local_path(settings.backup_dir),
        "logs_dir": settings.resolve_local_path(settings.logs_dir),
        "config_dir": settings.resolve_local_path(Path("config")),
    }


def init_desktop_paths() -> dict[str, Path]:
    paths = desktop_paths()
    for key, path in paths.items():
        if key == "database_file":
            path.parent.mkdir(parents=True, exist_ok=True)
            continue
        path.mkdir(parents=True, exist_ok=True)

    settings_file = paths["config_dir"] / "settings.json"
    if not settings_file.exists():
        settings_file.write_text(
            json.dumps(
                {
                    "app_edition": settings.app_edition,
                    "database_engine": settings.effective_database_engine,
                    "data_dir": str(paths["data_dir"]),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return paths


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    created_paths = init_desktop_paths()
    for name, path in created_paths.items():
        print(f"{name}={path}")
