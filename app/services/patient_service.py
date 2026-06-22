from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.diagnosis_history import DiagnosisHistory
from app.models.patient import Patient
from app.schemas.patients import DiagnosisRecordResponse, PatientHistoryResponse, PatientSummary


class PatientService:
    @staticmethod
    def search(db: Session, query: str) -> list[PatientSummary]:
        pattern = f"%{query.strip()}%"
        patients = db.scalars(
            select(Patient).where(
                or_(
                    Patient.pid.ilike(pattern),
                    Patient.hn.ilike(pattern),
                    Patient.citizen_id.ilike(pattern),
                    Patient.full_name.ilike(pattern),
                )
            )
        ).all()
        return [PatientSummary.model_validate(patient, from_attributes=True) for patient in patients]

    @staticmethod
    def history(db: Session, patient_id: int) -> PatientHistoryResponse:
        patient = db.get(Patient, patient_id)
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")
        history = db.scalars(
            select(DiagnosisHistory)
            .where(DiagnosisHistory.patient_id == patient_id)
            .order_by(DiagnosisHistory.visit_date.desc())
        ).all()
        return PatientHistoryResponse(
            patient=PatientSummary.model_validate(patient, from_attributes=True),
            history=[DiagnosisRecordResponse.model_validate(item, from_attributes=True) for item in history],
        )
