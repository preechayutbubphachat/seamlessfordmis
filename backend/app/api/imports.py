import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.write_lock import sqlite_write_lock
from app.dependencies import get_db
from app.schemas.import_job import SyncMainDatasetResponse
from app.schemas.system import SourceCheckResponse
from app.services.excel_main_import_service import ExcelMainImportService
from app.services.source_sync_service import SourceSyncService


router = APIRouter(prefix="/api/system", tags=["imports"])
logger = logging.getLogger(__name__)


@router.post("/check-source-update", response_model=SourceCheckResponse)
def check_source_update(db: Session = Depends(get_db)) -> SourceCheckResponse:
    logger.info("api.check_source_update.start")
    try:
        response = SourceSyncService.check_source_update(db)
        logger.info(
            "api.check_source_update.success changed=%s source_file_count=%s",
            response.changed,
            response.source_file_count,
        )
        return response
    except Exception as exc:
        logger.exception("api.check_source_update.failed")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถตรวจสถานะไฟล์ต้นทางได้: {exc}") from exc


@router.post("/sync-main-dataset", response_model=SyncMainDatasetResponse)
def sync_main_dataset(db: Session = Depends(get_db)) -> SyncMainDatasetResponse:
    logger.info("api.sync_main_dataset.start")
    try:
        with sqlite_write_lock():
            response = ExcelMainImportService.sync_main_dataset(db)
        logger.info("api.sync_main_dataset.success import_job_id=%s status=%s", response.import_job_id, response.status)
        return response
    except FileNotFoundError as exc:
        logger.warning("api.sync_main_dataset.not_found error=%s", exc)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("api.sync_main_dataset.failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync-disease-screening-database", response_model=SyncMainDatasetResponse)
def sync_disease_screening_database(db: Session = Depends(get_db)) -> SyncMainDatasetResponse:
    return sync_main_dataset(db)
