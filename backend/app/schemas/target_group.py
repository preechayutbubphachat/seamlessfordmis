from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import SourceFileResponse, TargetGroupPreviewRow, ValidationIssue


class TargetGroupSheetResponse(BaseModel):
    sheet_id: UUID
    source_file_id: UUID | None = None
    sheet_name: str
    sheet_index: int
    sheet_type: str
    row_count: int = 0
    column_names: list[str] = Field(default_factory=list)
    classification_confidence: float | None = None
    notes: str | None = None


class TargetGroupImportSummaryResponse(BaseModel):
    total_uploaded_files: int = 0
    total_rows: int = 0
    parsed_rows: int = 0
    valid_cid_rows: int = 0
    invalid_cid_rows: int = 0
    missing_cid_rows: int = 0
    duplicate_cid_rows: int = 0
    warning_rows: int = 0
    failed_rows: int = 0


class TargetGroupUploadResponse(BaseModel):
    group_id: UUID
    group_name: str
    parse_status: str
    source_file_count: int
    total_rows: int
    import_summary: TargetGroupImportSummaryResponse
    uploaded_files: list[SourceFileResponse] = Field(default_factory=list)
    sheets: list[TargetGroupSheetResponse] = Field(default_factory=list)
    preview_rows: list[TargetGroupPreviewRow] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    uploaded_at: datetime


class ConfirmImportResponse(BaseModel):
    group_id: UUID
    parse_status: str
    match_status: str


class RunMatchResponse(BaseModel):
    group_id: UUID
    match_status: str
    matched_rows: int
    not_found_rows: int
    ambiguous_rows: int
    needs_review_rows: int


class DiseaseOptionResponse(BaseModel):
    key: str
    label: str
    icd10_code: str | None = None
    raw_name: str | None = None


class MatchSummaryResponse(BaseModel):
    matched: int = 0
    not_found: int = 0
    ambiguous: int = 0
    needs_review: int = 0
    pending: int = 0


class TargetGroupListItemResponse(BaseModel):
    group_id: UUID
    group_name: str
    source_file_name: str
    source_file_type: str
    source_file_count: int = 1
    parse_status: str
    match_status: str
    total_rows: int
    invalid_rows: int
    import_summary: TargetGroupImportSummaryResponse
    match_summary: MatchSummaryResponse
    uploaded_at: datetime


class TargetGroupDetailResponse(BaseModel):
    group_id: UUID
    group_name: str
    source_file_name: str
    source_file_type: str
    source_file_hash: str
    source_set_hash: str | None = None
    source_file_count: int = 1
    parse_status: str
    match_status: str
    total_rows: int
    invalid_rows: int
    import_summary: TargetGroupImportSummaryResponse
    match_summary: MatchSummaryResponse
    uploaded_files: list[SourceFileResponse] = Field(default_factory=list)
    sheets: list[TargetGroupSheetResponse] = Field(default_factory=list)
    preview_rows: list[TargetGroupPreviewRow] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    uploaded_at: datetime


class UpdateGroupRequest(BaseModel):
    group_name: str = Field(..., min_length=1, max_length=200)


# Returned by POST /{group_id}/add-files — same shape as detail so the
# frontend can refresh the group state from a single response.
AddFilesResponse = TargetGroupDetailResponse


class TargetGroupValidationSummaryResponse(BaseModel):
    group_id: UUID
    total_rows: int
    invalid_rows: int
    missing_cid_rows: int = 0
    duplicate_cid_rows: int = 0
    review_required_rows: int
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
