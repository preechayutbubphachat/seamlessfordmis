from datetime import date

from pydantic import BaseModel


class MatchRunResponse(BaseModel):
    job_id: int
    status: str
    matched_rows: int
    review_rows: int
    unmatched_rows: int


class TargetGroupResultResponse(BaseModel):
    id: int
    row_number: int
    patient_id: int | None = None
    full_name: str | None = None
    pid: str | None = None
    hn: str | None = None
    match_method: str
    match_status: str
    selected_disease_key: str | None = None
    selected_disease_keys: list[str] = []
    result_status: str | None = None
    has_disease_history: bool | None = None
    latest_visit_date: date | None = None
    visit_count: int | None = None
    days_since_latest_visit: int | None = None
    years_since_latest_visit: float | None = None
    matched_disease_keys: list[str] = []
    matched_disease_labels: list[str] = []
    matched_service_items: list[str] = []
    flags: list[dict]


class GroupedDiseaseResponse(BaseModel):
    disease_key: str
    disease_group_label: str | None = None
    total_rows: int
    matched_rows: int
    needs_review_rows: int
    disease_positive_rows: int
    disease_unknown_rows: int


class SearchResultResponse(BaseModel):
    group_job_id: int
    filters: dict
    results: list[TargetGroupResultResponse]


class ExportResponse(BaseModel):
    job_id: int
    filename: str
    export_path: str
    row_count: int


class DiseaseSelectionRequest(BaseModel):
    disease_keys: list[str]


class DiseaseMappingOptionResponse(BaseModel):
    normalized_disease_key: str
    disease_group_label: str
    group_type: str
    diagnosis_code: str | None = None
    disease_name_raw: str | None = None
