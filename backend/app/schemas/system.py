from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import FileFingerprint, SourceFileResponse


class SystemStatusResponse(BaseModel):
    dataset_ready: bool
    source_file_exists: bool
    source_file_changed: bool
    source_file_count: int = 0
    source_set_hash: str | None = None
    latest_import_job_id: UUID | None = None
    import_status: str | None = None
    row_counts: dict[str, int] = Field(default_factory=dict)
    fingerprint: FileFingerprint | None = None
    source_files: list[SourceFileResponse] = Field(default_factory=list)


class SourceCheckResponse(BaseModel):
    changed: bool
    reason: str
    source_file_count: int = 0
    source_set_hash: str | None = None
    fingerprint: FileFingerprint | None = None
    files: list[SourceFileResponse] = Field(default_factory=list)
    previous_import: dict[str, Any] | None = None
