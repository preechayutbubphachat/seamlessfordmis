from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.diagnosis_history import DiagnosisHistory
from app.models.import_job import ImportJob, ImportJobStatus
from app.models.patient import Patient
from app.schemas.imports import SourceCheckResponse
from app.services.file_hash_service import FileHashService


class SourceSyncService:
    @staticmethod
    def get_source_files() -> list:
        return sorted(
            [
                path
                for path in settings.source_data_dir.glob(settings.source_data_pattern)
                if path.is_file()
            ],
            key=lambda path: path.name,
        )

    @staticmethod
    def get_latest_completed_job(db: Session) -> ImportJob | None:
        return db.scalar(
            select(ImportJob)
            .where(ImportJob.status == ImportJobStatus.completed)
            .order_by(desc(ImportJob.completed_at), desc(ImportJob.id))
            .limit(1)
        )

    @classmethod
    def check_source_change(cls, db: Session) -> SourceCheckResponse:
        source_files = cls.get_source_files()
        latest_job = cls.get_latest_completed_job(db)

        if not source_files:
            return SourceCheckResponse(
                has_source_file=False,
                changed=False,
                reason="No source Excel file found in data directory",
                latest_job_id=latest_job.id if latest_job else None,
            )

        fingerprints = [FileHashService.fingerprint(path) for path in source_files]
        manifest_hash = FileHashService.manifest_hash(fingerprints)
        fingerprint = fingerprints[0]
        previous = None
        changed = True
        reason = "Source file batch has not been imported yet"

        if latest_job:
            previous = {
                "filename": latest_job.source_filename,
                "sha256": latest_job.source_hash_sha256,
                "manifest_hash_sha256": latest_job.source_manifest_hash_sha256,
                "size_bytes": latest_job.source_size_bytes,
                "file_count": latest_job.source_file_count,
                "modified_at": latest_job.source_modified_at.isoformat(),
            }
            if latest_job.source_manifest_hash_sha256 == manifest_hash:
                changed = False
                reason = "Batch manifest hash matches latest completed import"
            else:
                reason = "Batch manifest hash changed from latest completed import"

        return SourceCheckResponse(
            has_source_file=True,
            changed=changed,
            reason=reason,
            latest_job_id=latest_job.id if latest_job else None,
            fingerprint=fingerprint,
            manifest_hash_sha256=manifest_hash,
            file_count=len(fingerprints),
            files=fingerprints,
            previous_fingerprint=previous,
        )

    @classmethod
    def dataset_ready(cls, db: Session) -> bool:
        source_check = cls.check_source_change(db)
        if not source_check.has_source_file or source_check.changed:
            return False
        patient_count = db.scalar(select(func.count()).select_from(Patient)) or 0
        history_count = db.scalar(select(func.count()).select_from(DiagnosisHistory)) or 0
        return patient_count > 0 and history_count > 0
