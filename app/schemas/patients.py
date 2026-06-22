from datetime import date

from pydantic import BaseModel


class PatientSummary(BaseModel):
    id: int
    pid: str | None = None
    citizen_id: str | None = None
    hn: str | None = None
    full_name: str | None = None
    birth_date: date | None = None


class DiagnosisRecordResponse(BaseModel):
    visit_date: date | None = None
    diagnosis_code: str | None = None
    disease_name_raw: str | None = None
    normalized_disease_key: str | None = None
    encounter_type: str | None = None
    provider_name: str | None = None


class PatientHistoryResponse(BaseModel):
    patient: PatientSummary
    history: list[DiagnosisRecordResponse]
