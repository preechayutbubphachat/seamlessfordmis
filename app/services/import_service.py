from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.importers.excel_importer import ExcelImporter, ParsedWorkbookRow
from app.models.diagnosis_history import DiagnosisHistory
from app.models.import_job import ImportJob, ImportJobSourceFile, ImportJobStatus
from app.models.patient import Patient
from app.models.staging_history_record import StagingHistoryRecord
from app.schemas.common import AuditLogCreate, ValidationIssue
from app.schemas.imports import SyncResponse
from app.services.audit_service import AuditService
from app.services.disease_mapping_service import DiseaseMappingService
from app.services.file_hash_service import FileHashService
from app.services.source_sync_service import SourceSyncService
from app.services.validation_service import ValidationService
from app.utils.normalizers import normalize_name


class ImportService:
    @classmethod
    def sync_main_dataset(cls, db: Session, actor: str = "system") -> SyncResponse:
        source_files = SourceSyncService.get_source_files()
        if not source_files:
            raise FileNotFoundError("Source Excel files not found in data directory")

        fingerprints = [FileHashService.fingerprint(path) for path in source_files]
        manifest_hash = FileHashService.manifest_hash(fingerprints)
        first_fingerprint = fingerprints[0]
        all_rows: list[ParsedWorkbookRow] = []

        for file_path in source_files:
            all_rows.extend(ExcelImporter.read_workbook_rows(file_path))

        job = ImportJob(
            status=ImportJobStatus.running,
            source_filename=first_fingerprint.filename,
            source_path=first_fingerprint.path,
            source_hash_sha256=first_fingerprint.sha256,
            source_manifest_hash_sha256=manifest_hash,
            source_size_bytes=first_fingerprint.size_bytes,
            source_file_count=len(fingerprints),
            source_modified_at=max(item.modified_at for item in fingerprints),
            started_at=datetime.utcnow(),
            total_rows=len(all_rows),
            metadata_json={
                "source_mode": "batch",
                "sheet_name": "Individual",
                "source_filenames": [item.filename for item in fingerprints],
            },
        )
        db.add(job)
        db.flush()

        for sequence_no, fingerprint in enumerate(fingerprints, start=1):
            db.add(
                ImportJobSourceFile(
                    import_job_id=job.id,
                    filename=fingerprint.filename,
                    file_path=fingerprint.path,
                    file_hash_sha256=fingerprint.sha256,
                    file_size_bytes=fingerprint.size_bytes,
                    file_modified_at=fingerprint.modified_at,
                    sequence_no=sequence_no,
                )
            )

        validation_issues: list[ValidationIssue] = []

        try:
            cls._load_staging_rows(db, job.id, all_rows, validation_issues)
            imported_rows = cls._merge_staging_to_production(db, job.id)
            job.status = ImportJobStatus.completed
            job.imported_rows = imported_rows
            job.error_rows = len(validation_issues)
            job.completed_at = datetime.utcnow()

            AuditService.log(
                db,
                AuditLogCreate(
                    actor=actor,
                    action="main_dataset_synced",
                    entity_type="import_job",
                    entity_id=str(job.id),
                    details_json={
                        "manifest_hash_sha256": manifest_hash,
                        "file_count": len(fingerprints),
                        "imported_rows": imported_rows,
                        "error_rows": len(validation_issues),
                    },
                    new_value_json={
                        "status": job.status.value,
                        "manifest_hash_sha256": manifest_hash,
                        "file_count": len(fingerprints),
                        "imported_rows": imported_rows,
                        "error_rows": len(validation_issues),
                    },
                    message="Main dataset synchronized from workbook batch",
                ),
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            db.add(job)
            job.status = ImportJobStatus.failed
            job.error_message = str(exc)
            job.completed_at = datetime.utcnow()
            db.commit()
            raise

        return SyncResponse(
            job_id=job.id,
            status=job.status.value,
            total_rows=job.total_rows or 0,
            imported_rows=job.imported_rows or 0,
            error_rows=job.error_rows or 0,
            fingerprint=first_fingerprint,
            manifest_hash_sha256=manifest_hash,
            file_count=len(fingerprints),
            validation_issues=validation_issues,
        )

    @classmethod
    def _load_staging_rows(
        cls,
        db: Session,
        job_id: int,
        workbook_rows: list[ParsedWorkbookRow],
        validation_issues: list[ValidationIssue],
    ) -> None:
        for parsed in workbook_rows:
            normalized, issues = ValidationService.validate_history_row(parsed.row_number, parsed.values)
            validation_issues.extend(issues)
            disease_key = DiseaseMappingService.resolve_disease_key(db, normalized["diagnosis_code"], normalized["disease_name_raw"])
            raw_payload = {
                **parsed.values,
                "source_filename": parsed.source_filename,
                "source_sheet_name": parsed.source_sheet_name,
            }
            staging = StagingHistoryRecord(
                import_job_id=job_id,
                row_number=parsed.row_number,
                source_filename=parsed.source_filename,
                source_sheet_name=parsed.source_sheet_name,
                raw_payload=raw_payload,
                pid=normalized["pid"],
                citizen_id=normalized["citizen_id"],
                hn=normalized["hn"],
                full_name=normalized["full_name"],
                birth_date=normalized["birth_date"],
                visit_date=normalized["visit_date"],
                diagnosis_code=normalized["diagnosis_code"],
                disease_name_raw=normalized["disease_name_raw"],
                normalized_disease_key=disease_key,
                validation_errors=[issue.model_dump() for issue in issues],
                is_valid=not issues,
                review_required=bool(normalized["full_name"] and not any([normalized["pid"], normalized["citizen_id"], normalized["hn"]])),
                notes=normalized.get("claim_status"),
            )
            db.add(staging)
        db.flush()

    @classmethod
    def _merge_staging_to_production(cls, db: Session, job_id: int) -> int:
        valid_rows = db.scalars(
            select(StagingHistoryRecord).where(
                StagingHistoryRecord.import_job_id == job_id,
                StagingHistoryRecord.is_valid.is_(True),
            )
        ).all()

        db.execute(delete(DiagnosisHistory))
        db.execute(delete(Patient))
        db.flush()

        patient_index: dict[tuple[str, str, str, str], Patient] = {}
        imported_rows = 0

        for row in valid_rows:
            patient = cls._resolve_or_create_patient(db, patient_index, row, job_id)
            diagnosis = DiagnosisHistory(
                patient_id=patient.id,
                import_job_id=job_id,
                visit_date=row.visit_date,
                diagnosis_code=row.diagnosis_code,
                disease_name_raw=row.disease_name_raw,
                normalized_disease_key=row.normalized_disease_key,
                encounter_type=row.raw_payload.get("coverage_type"),
                provider_name=row.raw_payload.get("hsend"),
                source_filename=row.source_filename,
                source_sheet_name=row.source_sheet_name,
                source_row_number=row.row_number,
                raw_payload_json=row.raw_payload,
                notes=row.notes,
            )
            db.add(diagnosis)
            imported_rows += 1

        db.flush()
        return imported_rows

    @staticmethod
    def _resolve_or_create_patient(
        db: Session,
        patient_index: dict[tuple[str, str, str, str], Patient],
        row: StagingHistoryRecord,
        job_id: int,
    ) -> Patient:
        candidate_keys = [
            ("pid", row.pid or ""),
            ("citizen_id", row.citizen_id or ""),
            ("hn", row.hn or ""),
            ("name", normalize_name(row.full_name) or ""),
        ]
        for candidate in candidate_keys:
            if candidate[1]:
                cached = patient_index.get(candidate)
                if cached:
                    return cached

        patient = Patient(
            pid=row.pid,
            citizen_id=row.citizen_id,
            hn=row.hn,
            full_name=row.full_name or "UNKNOWN",
            normalized_name=normalize_name(row.full_name),
            birth_date=row.birth_date,
            source_import_job_id=job_id,
        )
        db.add(patient)
        db.flush()
        for candidate in candidate_keys:
            if candidate[1]:
                patient_index[candidate] = patient
        return patient
