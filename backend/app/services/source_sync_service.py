import logging
from pathlib import Path

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.disease_mapping import DiseaseMapping
from app.models.disease_screening_record import DiseaseScreeningRecord
from app.models.diagnosis_history import DiagnosisHistory
from app.models.import_job import ImportJob
from app.models.patient import Patient
from app.models.source_file import SourceFile
from app.schemas.common import FileFingerprint
from app.schemas.system import SourceCheckResponse, SystemStatusResponse
from app.services.file_hash_service import FileHashService
from app.utils.files import is_supported_source_file


logger = logging.getLogger(__name__)


class SourceSyncService:
    @staticmethod
    def get_source_files() -> list[Path]:
        if not settings.source_data_dir.exists():
            return []
        return sorted(
            [path for path in settings.source_data_dir.iterdir() if is_supported_source_file(path)],
            key=lambda item: item.name.lower(),
        )

    @staticmethod
    def latest_main_import_job(db: Session) -> ImportJob | None:
        return db.scalar(
            select(ImportJob)
            .where(ImportJob.source_type == "main_history")
            .order_by(desc(ImportJob.created_at), desc(ImportJob.id))
            .limit(1)
        )

    @classmethod
    def current_source_fingerprints(cls) -> list[FileFingerprint]:
        return [FileHashService.fingerprint(path) for path in cls.get_source_files()]

    @classmethod
    def check_source_update(cls, db: Session) -> SourceCheckResponse:
        fingerprints = cls.current_source_fingerprints()
        latest_job = cls.latest_main_import_job(db)
        logger.info(
            "source.check.start file_count=%s latest_job_id=%s",
            len(fingerprints),
            latest_job.id if latest_job else None,
        )

        if not fingerprints:
            return SourceCheckResponse(
                changed=False,
                reason="ไม่พบไฟล์ต้นทางของฐานข้อมูลการตรวจโรคในโฟลเดอร์ data/",
                source_file_count=0,
                files=[],
            )

        source_set_hash = FileHashService.manifest_hash(fingerprints)
        changed = True
        reason = "ยังไม่เคย sync ไฟล์ต้นทางชุดนี้"
        previous_import = None

        if latest_job is not None:
            previous_import = {
                "import_job_id": str(latest_job.id),
                "source_file_hash": latest_job.source_file_hash,
                "source_set_hash": latest_job.source_set_hash,
                "source_file_count": latest_job.source_file_count,
                "status": latest_job.status,
            }
            if latest_job.source_set_hash == source_set_hash:
                changed = False
                reason = "ไฟล์ต้นทางชุดปัจจุบันตรงกับการ sync ล่าสุด"
            else:
                reason = "ชุดไฟล์ต้นทางมีการเปลี่ยนแปลงและต้อง sync ใหม่"

        logger.info(
            "source.check changed=%s file_count=%s source_set_hash=%s latest_job_id=%s",
            changed,
            len(fingerprints),
            source_set_hash,
            latest_job.id if latest_job else None,
        )
        return SourceCheckResponse(
            changed=changed,
            reason=reason,
            source_file_count=len(fingerprints),
            source_set_hash=source_set_hash,
            fingerprint=fingerprints[0],
            files=[FileHashService.as_source_file_response(item) for item in fingerprints],
            previous_import=previous_import,
        )

    @classmethod
    def system_status(cls, db: Session) -> SystemStatusResponse:
        source_check = cls.check_source_update(db)
        latest_job = cls.latest_main_import_job(db)
        patient_count = db.scalar(select(func.count()).select_from(Patient)) or 0
        history_count = db.scalar(select(func.count()).select_from(DiagnosisHistory)) or 0
        screening_count = db.scalar(select(func.count()).select_from(DiseaseScreeningRecord)) or 0
        # disease_mapping = the disease/service catalog that powers the
        # "สร้างผลลัพธ์" options. Surfaced here for diagnostics (empty = options empty).
        disease_mapping_count = db.scalar(select(func.count()).select_from(DiseaseMapping)) or 0
        active_disease_mapping_count = (
            db.scalar(select(func.count()).select_from(DiseaseMapping).where(DiseaseMapping.is_active.is_(True))) or 0
        )
        logger.info(
            "source.system_status.counts latest_job_id=%s patients=%s diagnosis_history=%s disease_screening_records=%s disease_mapping=%s",
            latest_job.id if latest_job else None,
            patient_count,
            history_count,
            screening_count,
            disease_mapping_count,
        )

        source_files = []
        if latest_job is not None:
            source_files = [
                FileHashService.as_source_file_response(FileFingerprint(
                    filename=item.file_name,
                    path=item.file_path or "",
                    sha256=item.sha256,
                    size_bytes=item.size_bytes,
                    modified_at=item.source_modified_at or item.created_at,
                )).model_copy(update={
                    "file_id": item.id,
                    "file_type": item.file_type,
                    "parse_status": item.parse_status,
                    "row_count": item.row_count,
                    "warning_count": item.warning_count,
                    "error_message": item.error_message,
                    "modified_at": item.source_modified_at or item.created_at,
                    "discovered_at": item.created_at,
                })
                for item in db.scalars(
                    select(SourceFile)
                    .where(SourceFile.import_job_id == latest_job.id)
                    .order_by(SourceFile.file_name.asc())
                ).all()
            ]

        return SystemStatusResponse(
            dataset_ready=bool(
                latest_job
                and latest_job.status == "success"
                and not source_check.changed
                and screening_count
            ),
            source_file_exists=bool(source_check.files),
            source_file_changed=source_check.changed,
            source_file_count=source_check.source_file_count,
            source_set_hash=source_check.source_set_hash,
            latest_import_job_id=latest_job.id if latest_job else None,
            import_status=latest_job.status if latest_job else None,
            row_counts={
                "patients": patient_count,
                "diagnosis_history": history_count,
                "disease_screening_records": screening_count,
                "disease_mapping": disease_mapping_count,
                "active_disease_mapping": active_disease_mapping_count,
            },
            fingerprint=source_check.fingerprint,
            source_files=source_files or source_check.files,
        )
