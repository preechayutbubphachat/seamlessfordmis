from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.export_service import ExportService


router = APIRouter(prefix="/api/target-groups", tags=["exports"])


@router.get("/{group_id}/export")
def export_group_results(
    group_id: UUID,
    format: str = Query(default="xlsx"),
    selected_service_keys: list[str] = Query(default_factory=list),
    db: Session = Depends(get_db),
):
    try:
        artifact = ExportService.export_group_results(
            db,
            group_id,
            export_format=format,
            selected_service_keys=selected_service_keys,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(
        path=artifact.path,
        filename=artifact.filename,
        media_type=artifact.media_type,
    )
