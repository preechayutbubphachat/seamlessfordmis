from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.patient import PatientHistoryResponse, PatientSummaryResponse
from app.services.patient_query_service import PatientQueryService


router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("/search", response_model=list[PatientSummaryResponse])
def search_patients(query: str, db: Session = Depends(get_db)) -> list[PatientSummaryResponse]:
    return PatientQueryService.search(db, query)


@router.get("/{patient_id}/history", response_model=PatientHistoryResponse)
def get_patient_history(patient_id: UUID, db: Session = Depends(get_db)) -> PatientHistoryResponse:
    """Return screening history for a patient.

    Queries DiseaseScreeningRecord (new pipeline) first; falls back to
    DiagnosisHistory for data imported before Phase 2.
    """
    try:
        return PatientQueryService.history(db, patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
