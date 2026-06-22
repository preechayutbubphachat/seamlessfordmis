from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateResultsRequest(BaseModel):
    disease_keys: list[str] = Field(default_factory=list)


class GroupResultRowResponse(BaseModel):
    result_id: UUID
    target_row_id: UUID | None = None
    group_job_id: UUID
    patient_id: UUID | None = None
    normalized_cid: str | None = None
    matched_identifier: str | None = None
    matched_name_basis: str | None = None
    full_name: str | None = None
    age: int | None = None
    raw_age: str | None = None
    birth_date: date | None = None
    sex: str | None = None
    match_status: str
    match_method: str | None = None
    match_confidence: str | None = None
    person_link_status: str | None = None
    duplicate_reason: str | None = None
    review_required: bool = False
    canonical_person_key: str | None = None
    result_category: str
    result_status: str
    screening_status: str = "never_checked"
    overdue_threshold_years: int | None = None
    has_selected_service: bool
    matching_record_count: int
    matched_service_keys: list[str] = Field(default_factory=list)
    last_visit_date: date | None = None
    days_since_last_visit: int | None = None
    years_since_last_visit: float | None = None
    target_group_history_labels: str | None = None
    target_group_history_note: str | None = None
    target_group_history_last_visit_date: date | None = None
    history_found_in_screening_db: bool = False
    history_found_in_target_group_file: bool = False
    history_source_summary: str = "no_history_found"
    last_relevant_source: str | None = None
    # Phase C: explicit source-type for the latest relevant date.
    # Values: "screening_db" | "target_group_file" | None.
    # Identical to last_relevant_source; added under Phase C spec name so
    # the frontend can consume either field without a breaking change.
    latest_relevant_source_type: str | None = None
    target_group_nationality: str | None = None
    target_group_address: str | None = None
    source_file_id: UUID | None = None
    source_file_name: str | None = None
    source_sheet_name: str | None = None
    source_row_no: int | None = None
    source_origin_context: str | None = None
    provenance_summary_count: int = 0
    provenance_details: list[dict] = Field(default_factory=list)
    latest_source_file_name: str | None = None
    latest_source_sheet_name: str | None = None
    latest_source_row_no: int | None = None
    screening_db_history_count: int = 0
    target_group_history_count: int = 0
    target_group_history_events: list[dict] = Field(default_factory=list)
    warning_message: str | None = None


class ResultSummaryResponse(BaseModel):
    group_job_id: UUID
    total_target_people: int
    valid_identifier_people: int
    invalid_identifier_people: int
    non_thai_nationality_people: int = 0
    insufficient_identity_people: int = 0
    outside_target_scope_people: int = 0
    review_required_identity_people: int = 0
    people_with_selected_history: int
    people_without_selected_history: int
    never_checked_people: int = 0
    checked_but_overdue_people: int = 0
    checked_and_within_threshold_people: int = 0
    coverage_percent: float
    coverage_denominator: str = "valid_identifier_people"
    coverage_denominator_people: int
    overdue_threshold_years: int | None = None
    selected_service_count: int
    selected_service_keys: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None
    generated_source_set_hash: str | None = None
    # Normalization/classification version this cached result was generated with,
    # and whether it is older than the current logic (→ UI should prompt regenerate).
    normalization_version: int | None = None
    current_normalization_version: int | None = None
    requires_regeneration: bool = False


class ServiceBreakdownResponse(BaseModel):
    selected_service_key: str
    distinct_people_count: int
    matching_record_count: int


class GenerateResultsResponse(BaseModel):
    group_id: UUID
    generated_rows: int
    disease_keys: list[str]
    summary: ResultSummaryResponse
    breakdown: list[ServiceBreakdownResponse] = Field(default_factory=list)


class GroupResultsResponse(BaseModel):
    group_id: UUID
    summary: ResultSummaryResponse
    breakdown: list[ServiceBreakdownResponse] = Field(default_factory=list)
    results: list[GroupResultRowResponse] = Field(default_factory=list)
    page: int = 1
    page_size: int = 100
    total_filtered_rows: int = 0
    total_pages: int = 0
