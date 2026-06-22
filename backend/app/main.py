import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.db.write_lock import WriteBusyError
from app.api.exports import router as exports_router
from app.api.imports import router as imports_router
from app.api.patients import router as patients_router
from app.api.screening_database import router as screening_database_router
from app.api.system import router as system_router
from app.api.target_groups import router as target_groups_router
from app.config import settings
from app.db.init_db import init_db


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)
app.include_router(system_router)
app.include_router(imports_router)
app.include_router(screening_database_router)
app.include_router(target_groups_router)
app.include_router(patients_router)
app.include_router(exports_router)


@app.on_event("startup")
def startup_init_db() -> None:
    init_db()


# ---------------------------------------------------------------------------
# Friendly DB-contention errors (Desktop Local / SQLite).
# Never leak raw SQL to the UI; log the technical detail for developers.
# ---------------------------------------------------------------------------
@app.exception_handler(WriteBusyError)
async def write_busy_handler(request: Request, exc: WriteBusyError) -> JSONResponse:
    logger.warning("write_busy method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=423,
        content={"detail": exc.message, "error_type": "WriteBusyError", "path": request.url.path},
    )


@app.exception_handler(OperationalError)
async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    raw = str(getattr(exc, "orig", exc))
    if "database is locked" in raw.lower() or "database table is locked" in raw.lower():
        # Log full technical detail (incl. SQL) server-side only.
        logger.warning("sqlite_locked method=%s path=%s detail=%s", request.method, request.url.path, raw)
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "ฐานข้อมูลกำลังถูกใช้งานโดยงานอื่น กรุณารอสักครู่แล้วลองใหม่อีกครั้ง "
                    "หากยังพบปัญหาให้ปิดโปรแกรมแล้วเปิดใหม่"
                ),
                "error_type": "DatabaseLocked",
                "path": request.url.path,
            },
        )
    logger.exception("operational_error method=%s path=%s", request.method, request.url.path)
    detail = "เกิดข้อผิดพลาดเกี่ยวกับฐานข้อมูล"
    if settings.include_error_details:
        detail = f"{detail}: {raw}"
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "error_type": "OperationalError", "path": request.url.path},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app_edition": settings.app_edition,
        "database_engine": settings.effective_database_engine,
    }


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    logger.info("request.start method=%s path=%s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("request.failed method=%s path=%s error=%s", request.method, request.url.path, exc)
        detail = "เกิดข้อผิดพลาดภายในระบบ"
        if settings.include_error_details:
            detail = f"{detail}: {exc}"
        return JSONResponse(
            status_code=500,
            content={
                "detail": detail,
                "error_type": exc.__class__.__name__,
                "path": request.url.path,
            },
        )

    logger.info("request.end method=%s path=%s status=%s", request.method, request.url.path, response.status_code)
    # D4.7: API responses must never be cached by the browser — stale cached
    # payloads (e.g. empty disease-options) would freeze the desktop UI state.
    if request.url.path.startswith(("/api", "/health")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ---------------------------------------------------------------------------
# D4: Desktop Local Edition — serve the static frontend bundle (if built).
# Active ONLY when APP_EDITION=desktop_local AND frontend/out exists, so the
# Docker/LAN edition (Next.js server on :3020) is completely unaffected.
# The mount is registered LAST so all API routes, /health and /docs win first.
# Never serves anything outside frontend/out (data/ stays private).
# ---------------------------------------------------------------------------
def _desktop_static_dir():
    from pathlib import Path

    out_dir = Path(__file__).resolve().parents[2] / "frontend" / "out"
    return out_dir if (out_dir / "index.html").is_file() else None


if settings.is_desktop_local:
    _static_dir = _desktop_static_dir()
    if _static_dir is not None:
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="desktop_frontend")
        logger.info("desktop static frontend mounted from %s", _static_dir)
    else:

        @app.get("/", include_in_schema=False)
        def desktop_root_placeholder() -> JSONResponse:
            return JSONResponse(
                {
                    "detail": "ยังไม่มี frontend static bundle — รัน `npm run desktop:build` ใน frontend/ ก่อน "
                    "หรือใช้ API docs ที่ /docs",
                    "docs_url": "/docs",
                }
            )
