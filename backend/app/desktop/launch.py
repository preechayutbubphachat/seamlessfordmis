"""D3/D4 Desktop Shell launcher.

Run:  python -m app.desktop.launch   (from the backend/ directory)

What it does:
- Forces desktop_local + SQLite environment (set BEFORE importing app.config)
- Initializes local data/log/export directories and the SQLite schema
- Binds the FastAPI backend to 127.0.0.1 only (never 0.0.0.0)
- Opens the browser at the best available entry URL (static app > dev server > /docs)
- Fails gracefully if the port is already in use

Safety (per project rules):
- No Docker, no telemetry, no auto-upload of logs
- No patient data or identifiers are printed or logged by this launcher
- No destructive action; this is NOT a production installer
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
DEFAULT_PORT = 8010
FRONTEND_PORT = 3020


def _force_desktop_local_env() -> None:
    """Set desktop-local env vars before app.config is imported.

    Environment variables take precedence over .env, so an existing
    LAN/PostgreSQL .env cannot leak into the desktop prototype.
    """
    backend_dir = Path(__file__).resolve().parents[2]
    data_dir = backend_dir.parent / "data"
    db_path = (data_dir / "seamlessfordmis.db").resolve()

    os.environ["APP_EDITION"] = "desktop_local"
    os.environ["DATABASE_ENGINE"] = "sqlite"
    os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    os.environ.setdefault("APP_ENV", "development")


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _open_browser_later(url: str, delay_seconds: float = 1.5) -> None:
    timer = threading.Timer(delay_seconds, webbrowser.open, args=(url,))
    timer.daemon = True
    timer.start()


def _static_frontend_ready() -> bool:
    """True when the D4 static bundle exists (frontend/out/index.html)."""
    out_index = Path(__file__).resolve().parents[3] / "frontend" / "out" / "index.html"
    return out_index.is_file()


def _pick_entry_url(backend_port: int) -> str:
    """Choose what the browser opens (D4.5).

    Priority:
    1. DESKTOP_OPEN_URL env override (explicit, loopback only)
    2. Static frontend served by this backend (frontend/out built) -> root app
    3. Local Next.js dev frontend at 127.0.0.1:3020 if already running
    4. Backend Swagger /docs as fallback
    Never opens a non-loopback address.
    """
    override = os.environ.get("DESKTOP_OPEN_URL", "").strip()
    if override.startswith(("http://127.0.0.1", "http://localhost")):
        return override

    if _static_frontend_ready():
        return f"http://{HOST}:{backend_port}/"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        if sock.connect_ex((HOST, FRONTEND_PORT)) == 0:
            return f"http://{HOST}:{FRONTEND_PORT}"
    return f"http://{HOST}:{backend_port}/docs"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    _force_desktop_local_env()

    # Imports AFTER env is forced — app.config.settings is a module-level singleton.
    import uvicorn

    from app.config import settings
    from app.desktop.paths import init_desktop_paths

    if not settings.is_desktop_local or not settings.is_sqlite:
        print("ERROR: desktop launcher requires APP_EDITION=desktop_local and DATABASE_ENGINE=sqlite")
        return 2

    port = int(os.environ.get("DESKTOP_PORT", DEFAULT_PORT))
    if not _port_available(HOST, port):
        print(f"ERROR: port {port} on {HOST} is already in use.")
        print("  - ปิดโปรแกรมที่ใช้ port นี้อยู่ หรือ")
        print(f"  - ตั้งค่า DESKTOP_PORT เป็นเลขอื่น เช่น  set DESKTOP_PORT={port + 1}  แล้วรันใหม่")
        return 1

    paths = init_desktop_paths()
    entry_url = _pick_entry_url(port)

    # Safe structured log — identifiers/payloads are never printed here.
    print("=" * 60)
    print("seamlessfordmis — Desktop Shell (D4, not production)")
    print("=" * 60)
    print(f"  app_edition     : {settings.app_edition}")
    print(f"  database_engine : {settings.effective_database_engine}")
    print(f"  database_file   : {paths['database_file']}")
    print(f"  data_dir        : {paths['data_dir']}")
    print(f"  log_dir         : {paths['logs_dir']}")
    print(f"  backend_url     : http://{HOST}:{port}  (local only, no LAN binding)")
    print(f"  opened_url      : {entry_url}")
    if entry_url.endswith("/docs"):
        print("  (ยังไม่มี static frontend bundle และ dev server ไม่ได้รัน — เปิด API docs แทน;")
        print("   ทางเลือก: รัน `npm run desktop:build` ใน frontend/ แล้วเปิด launcher ใหม่)")
    print("  กด Ctrl+C เพื่อหยุดการทำงาน")
    print("=" * 60)

    _open_browser_later(entry_url)

    # access_log disabled: query strings may contain identifiers; keep logs free
    # of patient data per project safety rules.
    uvicorn.run("app.main:app", host=HOST, port=port, log_level="info", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
