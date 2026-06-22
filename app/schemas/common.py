from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class AuditLogCreate(BaseModel):
    actor: str = "system"
    action: str
    entity_type: str
    entity_id: str | None = None
    details_json: dict[str, Any] = {}
    old_value_json: dict[str, Any] | None = None
    new_value_json: dict[str, Any] | None = None
    ip_address: str | None = None
    correlation_id: str | None = None
    message: str | None = None


class FileFingerprint(BaseModel):
    filename: str
    path: str
    sha256: str
    size_bytes: int
    modified_at: datetime


class ValidationIssue(BaseModel):
    row_number: int
    field: str
    message: str


class LatestVisitMetrics(BaseModel):
    latest_visit_date: date | None = None
    visit_count: int | None = None
    days_since_latest_visit: int | None = None
    years_since_latest_visit: int | None = None
