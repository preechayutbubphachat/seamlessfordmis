from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class FileFingerprint(BaseModel):
    filename: str
    path: str
    sha256: str
    size_bytes: int
    modified_at: datetime


class SourceFileResponse(BaseModel):
    file_id: UUID | None = None
    file_name: str
    file_path: str | None = None
    file_type: str
    sha256: str
    size_bytes: int
    modified_at: datetime | None = None
    parse_status: str | None = None
    row_count: int | None = None
    warning_count: int | None = None
    error_message: str | None = None
    parse_error_summary: str | None = None
    discovered_at: datetime | None = None


class ValidationIssue(BaseModel):
    row_id: UUID | None = None
    row_no: int
    source_file_id: UUID | None = None
    source_file_name: str | None = None
    source_row_no: int | None = None
    field: str
    message: str


class AuditLogCreate(BaseModel):
    actor: str | None = "system"
    action: str
    entity_type: str
    entity_id: str
    old_value_json: dict[str, Any] | None = None
    new_value_json: dict[str, Any] | None = None
    ip_address: str | None = None


class TargetGroupPreviewRow(BaseModel):
    row_id: UUID | None = None
    row_no: int
    source_file_id: UUID | None = None
    source_file_name: str | None = None
    source_row_no: int | None = None
    normalized_cid: str | None = None
    parse_status: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)


class VisitMetrics(BaseModel):
    latest_visit_date: date | None = None
    visit_count: int | None = None
    days_since_latest_visit: int | None = None
    years_since_latest_visit: float | None = None


class UUIDResponse(BaseModel):
    id: UUID
