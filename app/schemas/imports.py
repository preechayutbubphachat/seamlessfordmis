from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import FileFingerprint, ValidationIssue


class SourceCheckResponse(BaseModel):
    has_source_file: bool
    changed: bool
    reason: str
    latest_job_id: int | None = None
    fingerprint: FileFingerprint | None = None
    manifest_hash_sha256: str | None = None
    file_count: int = 0
    files: list[FileFingerprint] = []
    previous_fingerprint: dict[str, Any] | None = None


class SyncResponse(BaseModel):
    job_id: int
    status: str
    total_rows: int
    imported_rows: int
    error_rows: int
    fingerprint: FileFingerprint
    manifest_hash_sha256: str
    file_count: int
    validation_issues: list[ValidationIssue]


class TargetGroupUploadResponse(BaseModel):
    job_id: int
    group_name: str
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    preview_rows: list[dict[str, Any]]
    validation_issues: list[ValidationIssue]
    uploaded_at: datetime


class ConfirmTargetGroupResponse(BaseModel):
    job_id: int
    status: str
    valid_rows: int
    invalid_rows: int


class TargetGroupJobResponse(BaseModel):
    job_id: int
    group_name: str
    status: str
    parse_status: str | None = None
    match_status: str | None = None
    original_filename: str
    source_file_type: str | None = None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    review_rows: int
