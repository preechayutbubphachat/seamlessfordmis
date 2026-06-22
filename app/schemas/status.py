from pydantic import BaseModel

from app.schemas.common import FileFingerprint


class DatasetStatusResponse(BaseModel):
    dataset_ready: bool
    source_file_exists: bool
    source_file_changed: bool
    source_file_count: int = 0
    manifest_hash_sha256: str | None = None
    active_import_job_id: int | None = None
    last_completed_import_job_id: int | None = None
    import_status: str | None = None
    row_counts: dict[str, int]
    fingerprint: FileFingerprint | None = None
