import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.system import SystemStatusResponse
from app.services.source_sync_service import SourceSyncService


router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)) -> SystemStatusResponse:
    logger.info("api.system_status.start")
    try:
        response = SourceSyncService.system_status(db)
        logger.info(
            "api.system_status.success dataset_ready=%s source_file_count=%s latest_import_job_id=%s",
            response.dataset_ready,
            response.source_file_count,
            response.latest_import_job_id,
        )
        return response
    except Exception as exc:
        logger.exception("api.system_status.failed")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถโหลดสถานะระบบได้: {exc}") from exc
