from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.diagnosis_history import DiagnosisHistory
from app.models.patient import Patient
from app.schemas.imports import ConfirmTargetGroupResponse, SourceCheckResponse, SyncResponse, TargetGroupJobResponse, TargetGroupUploadResponse
from app.schemas.matching import DiseaseMappingOptionResponse, DiseaseSelectionRequest, ExportResponse, GroupedDiseaseResponse, MatchRunResponse, SearchResultResponse
from app.schemas.patients import PatientHistoryResponse, PatientSummary
from app.schemas.status import DatasetStatusResponse
from app.services.export_service import ExportService
from app.services.import_service import ImportService
from app.services.matching_service import MatchingService
from app.services.patient_service import PatientService
from app.services.source_sync_service import SourceSyncService
from app.services.target_group_service import TargetGroupService


router = APIRouter()


@router.get("/system/status", response_model=DatasetStatusResponse)
def system_status(db: Session = Depends(get_db)) -> DatasetStatusResponse:
    source_check = SourceSyncService.check_source_change(db)
    latest_job = SourceSyncService.get_latest_completed_job(db)
    return DatasetStatusResponse(
        dataset_ready=SourceSyncService.dataset_ready(db),
        source_file_exists=source_check.has_source_file,
        source_file_changed=source_check.changed,
        source_file_count=source_check.file_count,
        manifest_hash_sha256=source_check.manifest_hash_sha256,
        active_import_job_id=None,
        last_completed_import_job_id=latest_job.id if latest_job else None,
        import_status=latest_job.status.value if latest_job else None,
        row_counts={
            "patients": db.scalar(select(func.count()).select_from(Patient)) or 0,
            "diagnosis_history": db.scalar(select(func.count()).select_from(DiagnosisHistory)) or 0,
        },
        fingerprint=source_check.fingerprint,
    )


@router.get("/source/check", response_model=SourceCheckResponse)
def check_source_update(db: Session = Depends(get_db)) -> SourceCheckResponse:
    return SourceSyncService.check_source_change(db)


@router.post("/source/sync", response_model=SyncResponse)
def sync_main_dataset(db: Session = Depends(get_db)) -> SyncResponse:
    try:
        return ImportService.sync_main_dataset(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/target-groups/upload", response_model=TargetGroupUploadResponse)
def upload_target_group(
    group_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> TargetGroupUploadResponse:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel uploads are supported in MVP")
    # TODO: Add PDF parsing pipeline for target group imports.
    return TargetGroupService.upload_excel(db, group_name, file)


@router.get("/target-groups/{job_id}", response_model=TargetGroupJobResponse)
def get_target_group(job_id: int, db: Session = Depends(get_db)) -> TargetGroupJobResponse:
    try:
        return TargetGroupService.get_job(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/target-groups/{job_id}/confirm", response_model=ConfirmTargetGroupResponse)
def confirm_target_group(job_id: int, db: Session = Depends(get_db)) -> ConfirmTargetGroupResponse:
    try:
        return TargetGroupService.confirm_upload(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/target-groups/{job_id}/match", response_model=MatchRunResponse)
def run_matching(job_id: int, db: Session = Depends(get_db)) -> MatchRunResponse:
    try:
        return MatchingService.run_matching(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/target-groups/{job_id}/results", response_model=SearchResultResponse)
def generate_grouped_results(job_id: int, payload: DiseaseSelectionRequest, db: Session = Depends(get_db)) -> SearchResultResponse:
    try:
        return MatchingService.generate_disease_results(db, job_id, payload.disease_keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/target-groups/{job_id}/summary", response_model=list[GroupedDiseaseResponse])
def grouped_disease_summary(job_id: int, db: Session = Depends(get_db)) -> list[GroupedDiseaseResponse]:
    return MatchingService.grouped_disease_summary(db, job_id)


@router.get("/disease-mappings", response_model=list[DiseaseMappingOptionResponse])
def list_disease_mappings(db: Session = Depends(get_db)) -> list[DiseaseMappingOptionResponse]:
    return MatchingService.disease_options(db)


@router.get("/patients/search", response_model=list[PatientSummary])
def patient_search(query: str, db: Session = Depends(get_db)) -> list[PatientSummary]:
    return PatientService.search(db, query)


@router.get("/patients/{patient_id}/history", response_model=PatientHistoryResponse)
def patient_history(patient_id: int, db: Session = Depends(get_db)) -> PatientHistoryResponse:
    try:
        return PatientService.history(db, patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/target-groups/{job_id}/export", response_model=ExportResponse)
def export_results(job_id: int, db: Session = Depends(get_db)) -> ExportResponse:
    return ExportService.export_group_results(db, job_id)
