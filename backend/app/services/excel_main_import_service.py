import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.importers.excel_main_history_importer import ExcelMainHistoryImporter
from app.importers.pdf_scanned_importer import PdfScannedImporter
from app.importers.pdf_text_importer import PdfTextImporter
from app.matchers.disease_normalizer import DiseaseNormalizer
from app.models.import_job import ImportJob
from app.models.source_file import SourceFile
from app.models.staging_history_record import StagingHistoryRecord
from app.schemas.common import AuditLogCreate, ValidationIssue
from app.schemas.import_job import SyncMainDatasetResponse
from app.services.audit_log_service import AuditLogService
from app.services.file_hash_service import FileHashService
from app.services.merge_main_history_service import MergeMainHistoryService, MergeSummary
from app.services.source_sync_service import SourceSyncService
from app.services.staging_validation_service import StagingValidationService
from app.utils.dates import utcnow
from app.utils.files import detect_file_type


logger = logging.getLogger(__name__)


@dataclass
class StagingSummary:
    total_rows: int = 0
    parsed_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    warning_rows: int = 0

    @property
    def skipped_rows(self) -> int:
        return self.invalid_rows


class ExcelMainImportService:
    @classmethod
    def sync_main_dataset(cls, db: Session, actor: str = "system") -> SyncMainDatasetResponse:
        source_paths = SourceSyncService.get_source_files()
        if not source_paths:
            raise FileNotFoundError("ไม่พบไฟล์ต้นทางของฐานข้อมูลการตรวจโรคใน data/")

        fingerprints = [FileHashService.fingerprint(path) for path in source_paths]
        source_set_hash = FileHashService.manifest_hash(fingerprints)
        latest_modified_at = max((item.modified_at for item in fingerprints), default=None)
        latest_job = SourceSyncService.latest_main_import_job(db)

        if latest_job and latest_job.status == "success" and latest_job.source_set_hash == source_set_hash:
            logger.info("import.main_dataset.reuse import_job_id=%s source_set_hash=%s", latest_job.id, source_set_hash)
            AuditLogService.create_event(
                db,
                actor=actor,
                action="sync_disease_screening_database",
                entity_type="import_jobs",
                entity_id=str(latest_job.id),
                status="reused",
                context={
                    "source_file_count": latest_job.source_file_count,
                    "source_set_hash": latest_job.source_set_hash,
                },
            )
            db.commit()
            return SyncMainDatasetResponse(
                import_job_id=latest_job.id,
                status=latest_job.status,
                source_file_count=latest_job.source_file_count,
                source_set_hash=latest_job.source_set_hash,
                total_rows=latest_job.total_rows,
                parsed_rows=latest_job.parsed_rows,
                valid_rows=latest_job.valid_rows,
                invalid_rows=latest_job.invalid_rows,
                warning_rows=latest_job.warning_rows,
                merged_rows=latest_job.merged_rows,
                skipped_rows=latest_job.skipped_rows,
                duplicate_identifier_count=latest_job.duplicate_identifier_count,
                success_rows=latest_job.success_rows,
                failed_rows=latest_job.failed_rows,
                started_at=latest_job.started_at,
                finished_at=latest_job.finished_at,
                validation_issues=[],
            )

        job = ImportJob(
            source_type="main_history",
            source_file_name=fingerprints[0].filename if len(fingerprints) == 1 else f"{len(fingerprints)} files",
            source_file_path=str(source_paths[0].parent.resolve()),
            source_file_hash=fingerprints[0].sha256 if len(fingerprints) == 1 else source_set_hash,
            source_file_size=sum(item.size_bytes for item in fingerprints),
            source_file_modified_at=latest_modified_at,
            source_set_hash=source_set_hash,
            source_file_count=len(fingerprints),
            status="processing",
            started_at=utcnow(),
            created_by=actor,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        AuditLogService.create_event(
            db,
            actor=actor,
            action="sync_disease_screening_database",
            entity_type="import_jobs",
            entity_id=str(job.id),
            status="started",
            context={
                "source_file_count": job.source_file_count,
                "source_set_hash": job.source_set_hash,
            },
        )
        db.commit()

        validation_issues: list[ValidationIssue] = []
        summary = StagingSummary()

        try:
            for source_path, fingerprint in zip(source_paths, fingerprints, strict=True):
                source_file = SourceFile(
                    import_job_id=job.id,
                    file_name=fingerprint.filename,
                    file_path=fingerprint.path,
                    file_type=detect_file_type(source_path),
                    sha256=fingerprint.sha256,
                    size_bytes=fingerprint.size_bytes,
                    source_modified_at=fingerprint.modified_at,
                    parse_status="processing",
                )
                db.add(source_file)
                db.flush()

                file_summary, file_issues, file_status = cls._stage_source_file(db, source_path, source_file)
                validation_issues.extend(file_issues)
                summary.total_rows += file_summary.total_rows
                summary.parsed_rows += file_summary.parsed_rows
                summary.valid_rows += file_summary.valid_rows
                summary.invalid_rows += file_summary.invalid_rows
                summary.warning_rows += file_summary.warning_rows

                source_file.row_count = file_summary.total_rows
                source_file.warning_count = file_summary.warning_rows
                source_file.parse_status = file_status
                source_file.error_message = file_issues[0].message if file_issues else None
                db.add(source_file)
                logger.info(
                    "import.source_file file=%s type=%s rows=%s valid=%s invalid=%s warning=%s status=%s",
                    source_file.file_name,
                    source_file.file_type,
                    file_summary.total_rows,
                    file_summary.valid_rows,
                    file_summary.invalid_rows,
                    file_summary.warning_rows,
                    file_status,
                )

            job.total_rows = summary.total_rows
            job.parsed_rows = summary.parsed_rows
            job.valid_rows = summary.valid_rows
            job.invalid_rows = summary.invalid_rows
            job.warning_rows = summary.warning_rows
            job.skipped_rows = summary.skipped_rows
            job.failed_rows = summary.invalid_rows
            db.add(job)
            db.commit()

            merge_summary = MergeMainHistoryService.merge_import_job(db, job.id)
            job.status = "success"
            job.success_rows = merge_summary.merged_rows
            job.merged_rows = merge_summary.merged_rows
            job.duplicate_identifier_count = merge_summary.duplicate_identifier_count
            job.finished_at = utcnow()
            db.add(job)
            AuditLogService.create(
                db,
                AuditLogCreate(
                    actor=actor,
                    action="sync_disease_screening_database",
                    entity_type="import_jobs",
                    entity_id=str(job.id),
                    new_value_json={
                        "status": "success",
                        "source_file_count": job.source_file_count,
                        "source_set_hash": job.source_set_hash,
                        "total_rows": job.total_rows,
                        "parsed_rows": job.parsed_rows,
                        "valid_rows": job.valid_rows,
                        "invalid_rows": job.invalid_rows,
                        "warning_rows": job.warning_rows,
                        "merged_rows": job.merged_rows,
                        "skipped_rows": job.skipped_rows,
                        "duplicate_identifier_count": job.duplicate_identifier_count,
                    },
                ),
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            persisted_job = db.get(ImportJob, job.id)
            if persisted_job is not None:
                persisted_job.status = "failed"
                persisted_job.error_summary = str(exc)
                persisted_job.finished_at = utcnow()
                db.add(persisted_job)
                AuditLogService.create_event(
                    db,
                    actor=actor,
                    action="sync_disease_screening_database",
                    entity_type="import_jobs",
                    entity_id=str(persisted_job.id),
                    status="failed",
                    context={
                        "source_file_count": persisted_job.source_file_count,
                        "source_set_hash": persisted_job.source_set_hash,
                    },
                    error_summary=str(exc),
                )
                db.commit()
            logger.exception("import.main_dataset.failed import_job_id=%s", job.id)
            raise

        return SyncMainDatasetResponse(
            import_job_id=job.id,
            status=job.status,
            source_file_count=job.source_file_count,
            source_set_hash=job.source_set_hash,
            total_rows=job.total_rows,
            parsed_rows=job.parsed_rows,
            valid_rows=job.valid_rows,
            invalid_rows=job.invalid_rows,
            warning_rows=job.warning_rows,
            merged_rows=job.merged_rows,
            skipped_rows=job.skipped_rows,
            duplicate_identifier_count=job.duplicate_identifier_count,
            success_rows=job.success_rows,
            failed_rows=job.failed_rows,
            started_at=job.started_at,
            finished_at=job.finished_at,
            validation_issues=validation_issues[:50],
        )

    @classmethod
    def _stage_source_file(
        cls,
        db: Session,
        source_path: Path,
        source_file: SourceFile,
    ) -> tuple[StagingSummary, list[ValidationIssue], str]:
        file_type = detect_file_type(source_path)
        if file_type in {"excel", "csv"}:
            return cls._stage_excel_like_source_file(db, source_path, source_file)
        return cls._stage_pdf_source_file(db, source_path, source_file)

    @classmethod
    def _stage_excel_like_source_file(
        cls,
        db: Session,
        source_path: Path,
        source_file: SourceFile,
    ) -> tuple[StagingSummary, list[ValidationIssue], str]:
        rows = ExcelMainHistoryImporter.read_rows(source_path)
        issues: list[ValidationIssue] = []
        summary = StagingSummary(total_rows=len(rows), parsed_rows=len(rows))

        for parsed in rows:
            payload = parsed.values
            normalized, row_issues = StagingValidationService.validate_main_history_row(parsed.row_number, payload)
            warning_message = None
            disease_key = DiseaseNormalizer.resolve_key(
                db,
                normalized["diagnosis_code"],
                normalized["diagnosis_name"],
            )
            if disease_key is None and normalized["raw_service_type"]:
                warning_message = "ยังไม่พบ disease mapping สำหรับบริการนี้"

            validation_status = cls._classify_validation_status(row_issues=row_issues, warning_message=warning_message)
            if validation_status == "valid":
                summary.valid_rows += 1
            elif validation_status == "warning":
                summary.warning_rows += 1
            else:
                summary.invalid_rows += 1

            issues.extend(row_issues)
            db.add(
                cls._build_staging_history_record(
                    import_job_id=source_file.import_job_id,
                    source_file_id=source_file.id,
                    source_file_name=source_file.file_name,
                    source_row_no=parsed.row_number,
                    payload=payload,
                    normalized=normalized,
                    validation_status=validation_status,
                    row_issues=row_issues,
                    warning_message=warning_message,
                    disease_key=disease_key,
                    source_filename=parsed.source_filename,
                    source_sheet_name=parsed.source_sheet_name,
                )
            )

        db.flush()
        file_status = "warning" if summary.invalid_rows or summary.warning_rows else "parsed"
        return summary, issues, file_status

    @staticmethod
    def _classify_validation_status(*, row_issues: list[ValidationIssue], warning_message: str | None) -> str:
        if row_issues:
            return "invalid"
        if warning_message:
            return "warning"
        return "valid"

    @staticmethod
    def _build_staging_history_record(
        *,
        import_job_id,
        source_file_id,
        source_file_name: str,
        source_row_no: int,
        payload: dict,
        normalized: dict,
        validation_status: str,
        row_issues: list[ValidationIssue],
        warning_message: str | None,
        disease_key: str | None,
        source_filename: str,
        source_sheet_name: str,
    ) -> StagingHistoryRecord:
        confidence_flag = "low" if row_issues else "medium" if warning_message else "high"
        return StagingHistoryRecord(
            import_job_id=import_job_id,
            source_file_id=source_file_id,
            source_file_name=source_file_name,
            source_row_no=source_row_no,
            row_no=source_row_no,
            raw_person_identifier=normalized["raw_person_identifier"],
            raw_pid=payload.get("pid"),
            raw_citizen_id=payload.get("citizen_id") or payload.get("cid"),
            raw_hn=payload.get("hn"),
            raw_full_name=normalized["raw_full_name"],
            raw_birth_date=payload.get("birth_date") or payload.get("วันเกิด"),
            raw_visit_date=normalized["raw_visit_date"],
            raw_service_type=normalized["raw_service_type"],
            raw_hcode=normalized["raw_hcode"],
            raw_transaction_id=normalized["raw_transaction_id"],
            raw_rep_no=normalized["raw_rep_no"],
            raw_diagnosis_code=normalized.get("raw_diagnosis_code"),
            raw_diagnosis_name=normalized.get("raw_service_type"),
            raw_department=normalized.get("raw_department"),
            raw_doctor_name=normalized.get("raw_doctor_name"),
            parse_status="parsed",
            validation_status=validation_status,
            identifier_validation_status=normalized["identifier_validation_status"],
            date_validation_status=normalized["date_validation_status"],
            service_validation_status=normalized["service_validation_status"],
            confidence_flag=confidence_flag,
            error_message="; ".join(issue.message for issue in row_issues) or None,
            warning_message=warning_message,
            normalized_person_identifier=normalized["normalized_person_identifier"],
            normalized_pid=normalized.get("pid"),
            normalized_citizen_id=normalized.get("citizen_id"),
            normalized_hn=normalized.get("hn"),
            normalized_full_name=normalized.get("full_name"),
            normalized_birth_date=normalized.get("birth_date"),
            normalized_visit_date=normalized.get("visit_date"),
            normalized_service_key=normalized.get("normalized_service_key"),
            normalized_diagnosis_code=normalized.get("diagnosis_code"),
            normalized_diagnosis_name=normalized.get("diagnosis_name"),
            normalized_disease_key=disease_key,
            raw_json={
                **payload,
                "source_filename": source_filename,
                "source_sheet_name": source_sheet_name,
                "source_row_number": source_row_no,
            },
        )

    @classmethod
    def _stage_pdf_source_file(
        cls,
        db: Session,
        source_path: Path,
        source_file: SourceFile,
    ) -> tuple[StagingSummary, list[ValidationIssue], str]:
        issues: list[ValidationIssue] = []
        summary = StagingSummary()
        text_pages = PdfTextImporter.read_pages(source_path)
        has_text = any(page.text for page in text_pages)
        if has_text:
            summary.total_rows = len(text_pages)
            for page in text_pages:
                warning_message = page.warning_message or "TODO: PDF text import ยังไม่รองรับการแยกช่องข้อมูลฐานข้อมูลการตรวจโรคอย่างปลอดภัย"
                issues.append(ValidationIssue(row_no=page.page_number, field="pdf", message=warning_message))
                summary.invalid_rows += 1
                db.add(
                    StagingHistoryRecord(
                        import_job_id=source_file.import_job_id,
                        source_file_id=source_file.id,
                        source_file_name=source_file.file_name,
                        source_row_no=page.page_number,
                        row_no=page.page_number,
                        parse_status="parse_failed",
                        validation_status="invalid",
                        confidence_flag="low",
                        error_message=warning_message,
                        warning_message="TODO: future PDF parser/manual review flow",
                        raw_json={
                            "source_filename": source_file.file_name,
                            "source_page_number": page.page_number,
                            "raw_pdf_text": page.text,
                            "parse_warning": warning_message,
                            "import_mode": "pdf_text_import_v1",
                        },
                    )
                )
            db.flush()
            return summary, issues, "warning"

        scanned_pages = PdfScannedImporter.read_pages(source_path)
        summary.total_rows = len(scanned_pages)
        for page in scanned_pages:
            issues.append(ValidationIssue(row_no=page.page_number, field="pdf", message=page.warning_message))
            summary.invalid_rows += 1
            db.add(
                StagingHistoryRecord(
                    import_job_id=source_file.import_job_id,
                    source_file_id=source_file.id,
                    source_file_name=source_file.file_name,
                    source_row_no=page.page_number,
                    row_no=page.page_number,
                    parse_status="parse_failed",
                    validation_status="invalid",
                    confidence_flag="low",
                    error_message=page.warning_message,
                    warning_message="TODO: scanned PDF OCR/manual review support",
                    raw_json={
                        "source_filename": source_file.file_name,
                        "source_page_number": page.page_number,
                        "raw_pdf_text": None,
                        "parse_warning": page.warning_message,
                        "import_mode": "pdf_scanned_import_v1",
                    },
                )
            )
        db.flush()
        return summary, issues, "needs_review"
