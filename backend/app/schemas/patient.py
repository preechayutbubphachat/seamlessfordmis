from datetime import date
from uuid import UUID

from pydantic import BaseModel


class PatientSummaryResponse(BaseModel):
    id: UUID
    pid: str | None = None
    citizen_id: str | None = None
    hn: str | None = None
    full_name: str
    birth_date: date | None = None


class DiagnosisHistoryResponse(BaseModel):
    visit_date: date
    diagnosis_code: str | None = None
    diagnosis_name: str | None = None
    normalized_disease_key: str | None = None
    department: str | None = None
    doctor_name: str | None = None


class PatientHistoryResponse(BaseModel):
    patient: PatientSummaryResponse
    history: list[DiagnosisHistoryResponse]


# Phase C: per-record detail from disease_screening_records (new import pipeline table)
class ScreeningRecordResponse(BaseModel):
    record_id: UUID
    source_file_name: str | None = None
    source_row_no: int | None = None
    normalized_person_identifier: str
    full_name: str | None = None
    raw_service_type: str
    normalized_service_key: str
    visit_date: date


# Phase C: combined source-history response for a target group result row.
# Contains screening DB records + TG file history events in separate buckets
# so the UI can render them in clearly labelled sections.
class ResultSourceHistoryResponse(BaseModel):
    result_id: UUID
    normalized_cid: str | None = None
    full_name: str | None = None
    screening_db_records: list[ScreeningRecordResponse]
    target_group_history_events: list[dict]
    history_source_summary: str
