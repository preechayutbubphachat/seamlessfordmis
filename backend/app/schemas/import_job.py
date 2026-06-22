from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ValidationIssue


class SyncMainDatasetResponse(BaseModel):
    import_job_id: UUID
    status: str
    source_file_count: int = 0
    source_set_hash: str | None = None
    total_rows: int
    parsed_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    warning_rows: int = 0
    merged_rows: int = 0
    skipped_rows: int = 0
    duplicate_identifier_count: int = 0
    success_rows: int
    failed_rows: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
