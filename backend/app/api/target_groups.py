import logging
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.write_lock import sqlite_write_lock
from app.dependencies import get_db
from app.schemas.common import SourceFileResponse
from app.schemas.result import GenerateResultsRequest, GenerateResultsResponse, GroupResultsResponse, ResultSummaryResponse
from app.schemas.target_group import (
    AddFilesResponse,
    ConfirmImportResponse,
    DiseaseOptionResponse,
    RunMatchResponse,
    TargetGroupDetailResponse,
    TargetGroupListItemResponse,
    TargetGroupUploadResponse,
    TargetGroupValidationSummaryResponse,
    UpdateGroupRequest,
)
from app.services.patient_matching_service import PatientMatchingService
from app.services.result_generation_service import ResultGenerationService
from app.services.target_group_import_service import DuplicateUploadError, TargetGroupImportService


router = APIRouter(prefix="/api/target-groups", tags=["target-groups"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[TargetGroupListItemResponse])
def list_target_groups(db: Session = Depends(get_db)) -> list[TargetGroupListItemResponse]:
    return TargetGroupImportService.list_groups(db)


@router.get("/disease-options", response_model=list[DiseaseOptionResponse])
def get_disease_options(db: Session = Depends(get_db)) -> list[DiseaseOptionResponse]:
    return TargetGroupImportService.disease_options(db)


@router.post("/upload", response_model=TargetGroupUploadResponse)
def upload_target_group(
    group_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> TargetGroupUploadResponse:
    return upload_target_group_files(group_name=group_name, files=[file], db=db)


@router.post("/upload-files", response_model=TargetGroupUploadResponse)
def upload_target_group_files(
    group_name: str = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> TargetGroupUploadResponse:
    for file in files:
        if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls", ".csv", ".pdf")):
            raise HTTPException(status_code=400, detail="รองรับไฟล์ Excel, CSV และ PDF เท่านั้น")
    logger.info("api.target_groups.upload_files group_name=%s file_count=%s", group_name, len(files))
    started = perf_counter()
    try:
        with sqlite_write_lock():
            result = TargetGroupImportService.upload_files(db, group_name, files)
        logger.info(
            "api.target_groups.upload_files.done group_id=%s file_count=%s total_rows=%s duration_ms=%d status=%s",
            result.group_id,
            len(files),
            result.total_rows,
            int((perf_counter() - started) * 1000),
            result.parse_status,
        )
        return result
    except DuplicateUploadError as exc:
        # Not an error from the user's view — the import already exists. Return
        # 409 with the existing group id so the UI can open it (no duplicate job).
        logger.info(
            "api.target_groups.upload_files.duplicate group_id=%s duration_ms=%d",
            exc.group_id,
            int((perf_counter() - started) * 1000),
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "กลุ่มเป้าหมายนี้ถูกนำเข้าไปแล้ว สามารถเปิดดูจากรายการกลุ่มเป้าหมายล่าสุดได้",
                "group_id": str(exc.group_id),
                "parse_status": exc.parse_status,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{group_id}", response_model=TargetGroupDetailResponse)
def get_target_group(group_id: UUID, db: Session = Depends(get_db)) -> TargetGroupDetailResponse:
    try:
        return TargetGroupImportService.get_group_detail(db, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{group_id}", response_model=TargetGroupDetailResponse)
def update_target_group(group_id: UUID, body: UpdateGroupRequest, db: Session = Depends(get_db)) -> TargetGroupDetailResponse:
    try:
        return TargetGroupImportService.update_group_name(db, group_id, body.group_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{group_id}/add-files", response_model=AddFilesResponse)
def add_files_to_group(
    group_id: UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> AddFilesResponse:
    """Attach one or more new files to an existing target group.

    Never creates a new group — always operates on the specified group_id.
    Returns the updated group detail so the frontend can refresh state in one
    round trip.
    """
    for file in files:
        if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls", ".csv", ".pdf")):
            raise HTTPException(status_code=400, detail="รองรับไฟล์ Excel, CSV และ PDF เท่านั้น")
    logger.info("api.target_groups.add_files group_id=%s file_count=%s", group_id, len(files))
    try:
        with sqlite_write_lock():
            return TargetGroupImportService.add_files_to_group(db, group_id, files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{group_id}/files", response_model=list[SourceFileResponse])
def get_target_group_files(group_id: UUID, db: Session = Depends(get_db)) -> list[SourceFileResponse]:
    try:
        return TargetGroupImportService.get_group_files(db, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{group_id}/validation-summary", response_model=TargetGroupValidationSummaryResponse)
def get_target_group_validation_summary(group_id: UUID, db: Session = Depends(get_db)) -> TargetGroupValidationSummaryResponse:
    try:
        return TargetGroupImportService.get_validation_summary(db, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{group_id}/confirm-import", response_model=ConfirmImportResponse)
def confirm_import(group_id: UUID, db: Session = Depends(get_db)) -> ConfirmImportResponse:
    try:
        with sqlite_write_lock():
            return TargetGroupImportService.confirm_import(db, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{group_id}/run-match", response_model=RunMatchResponse)
def run_match(group_id: UUID, db: Session = Depends(get_db)) -> RunMatchResponse:
    try:
        with sqlite_write_lock():
            return PatientMatchingService.run(db, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{group_id}/generate-results", response_model=GenerateResultsResponse)
def generate_results(group_id: UUID, payload: GenerateResultsRequest, db: Session = Depends(get_db)) -> GenerateResultsResponse:
    try:
        with sqlite_write_lock():
            return ResultGenerationService.generate(db, group_id, payload.disease_keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{group_id}/results", response_model=GroupResultsResponse)
def get_group_results(
    group_id: UUID,
    overdue_years: int = Query(1, ge=1, le=20),
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(100, ge=1, le=500),
    include_all: bool = Query(False),
    view: str | None = Query(None),
    query: str | None = Query(None),
    overdue_enabled: bool = Query(False),
    sort_col: str | None = Query(None, description="Column key to sort by (e.g. full_name, age, last_visit_date)"),
    sort_dir: str | None = Query(None, pattern="^(asc|desc)$", description="Sort direction: asc or desc"),
    db: Session = Depends(get_db),
) -> GroupResultsResponse:
    return ResultGenerationService.get_results(
        db,
        group_id,
        overdue_years=overdue_years,
        page=page,
        page_size=page_size,
        include_all=include_all,
        view=view,
        query=query,
        overdue_enabled=overdue_enabled,
        sort_col=sort_col,
        sort_dir=sort_dir,
    )


@router.get("/{group_id}/result-summary", response_model=ResultSummaryResponse)
def get_group_result_summary(
    group_id: UUID,
    overdue_years: int = Query(1, ge=1, le=20),
    db: Session = Depends(get_db),
) -> ResultSummaryResponse:
    return ResultGenerationService.get_result_summary(db, group_id, overdue_years=overdue_years)



@router.get("/{group_id}/results/{result_id}/source-history")
def get_result_source_history(
    group_id: UUID,
    result_id: UUID,
    service_keys: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return both evidence sources for a single result row.

    Designed for the patient-detail modal (Phase C).  Returns:
    - screening_db_records: rows from disease_screening_records
    - target_group_history_events: rows from target_group_history_rows

    Works even when patient_id is NULL (TG-file-only person).
    service_keys filters both sources to the selected disease/service scope.
    """
    from app.schemas.patient import ResultSourceHistoryResponse
    from app.services.patient_query_service import PatientQueryService
    try:
        return PatientQueryService.source_history_for_result(
            db,
            result_id=result_id,
            selected_service_keys=service_keys or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
