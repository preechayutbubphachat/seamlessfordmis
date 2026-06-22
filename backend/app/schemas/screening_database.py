from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import SourceFileResponse


class ImportJobSummaryResponse(BaseModel):
    import_id: str
    status: str
    file_name: str
    file_type: str
    file_size: int | None = None
    detected_rows: int = 0
    success_rows: int = 0
    failed_rows: int = 0
    validation_error_count: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: str | None = None
    source_set_hash: str | None = None
    error_summary: str | None = None


class ImportJobListResponse(BaseModel):
    imports: list[ImportJobSummaryResponse] = Field(default_factory=list)
    total: int = 0


class ImportJobDetailResponse(ImportJobSummaryResponse):
    source_type: str
    source_file_hash: str | None = None
    source_file_path: str | None = None
    source_file_modified_at: datetime | None = None
    parsed_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    warning_rows: int = 0
    merged_rows: int = 0
    skipped_rows: int = 0
    duplicate_identifier_count: int = 0
    source_files: list[SourceFileResponse] = Field(default_factory=list)


class StageUploadResponse(BaseModel):
    status: str  # "staged" | "staged_pdf_needs_review"
    file_name: str
    file_type: str
    file_size: int
    message: str
    next_step: str
    needs_review: bool = False
