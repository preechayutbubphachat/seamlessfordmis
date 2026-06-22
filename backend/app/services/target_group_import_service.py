import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.importers.excel_target_group_importer import (
    ExcelTargetGroupImporter,
    HISTORY_SHEET,
    MIXED_SHEET,
    PERSON_IDENTITY_COLUMNS,
    ParsedTargetGroupRow,
    ParsedTargetGroupSheet,
    ParsedTargetGroupWorkbook,
    ROSTER_SHEET,
    UNKNOWN_SHEET,
)
from app.importers.pdf_target_group_importer import PdfTargetGroupImporter
from app.models.disease_mapping import DiseaseMapping
from app.models.target_group_history_row import TargetGroupHistoryRow
from app.models.target_group_job import TargetGroupJob
from app.models.target_group_job_file import TargetGroupJobFile
from app.models.target_group_row import TargetGroupRow
from app.models.target_group_sheet import TargetGroupSheet
from app.schemas.common import SourceFileResponse, TargetGroupPreviewRow, ValidationIssue
from app.schemas.target_group import (
    ConfirmImportResponse,
    DiseaseOptionResponse,
    MatchSummaryResponse,
    TargetGroupDetailResponse,
    TargetGroupImportSummaryResponse,
    TargetGroupListItemResponse,
    TargetGroupUploadResponse,
    TargetGroupValidationSummaryResponse,
)
from app.services.audit_log_service import AuditLogService
from app.services.file_hash_service import FileHashService
from app.services.staging_validation_service import StagingValidationService
from app.utils.files import detect_file_type


logger = logging.getLogger(__name__)


class DuplicateUploadError(Exception):
    """Raised when an identical file set + group name was already imported.

    Carries the existing group id so the API/UI can guide the user to the
    existing group instead of creating a duplicate target_group_jobs row
    (e.g. after a slow import made the client time out and the user retried).
    """

    def __init__(self, group_id, parse_status: str | None = None) -> None:
        self.group_id = group_id
        self.parse_status = parse_status
        super().__init__("กลุ่มเป้าหมายนี้ (ชื่อกลุ่ม + ชุดไฟล์เดียวกัน) ถูกนำเข้าไปแล้ว")


@dataclass
class TargetGroupImportSummary:
    total_uploaded_files: int = 0
    total_rows: int = 0
    parsed_rows: int = 0
    valid_cid_rows: int = 0
    invalid_cid_rows: int = 0
    missing_cid_rows: int = 0
    duplicate_cid_rows: int = 0
    warning_rows: int = 0
    failed_rows: int = 0

    def to_response(self) -> TargetGroupImportSummaryResponse:
        return TargetGroupImportSummaryResponse(**self.__dict__)


class TargetGroupImportService:
    @classmethod
    def upload(cls, db: Session, group_name: str, upload_file: UploadFile, actor: str = "system") -> TargetGroupUploadResponse:
        return cls.upload_files(db, group_name, [upload_file], actor=actor)

    @classmethod
    def upload_files(
        cls,
        db: Session,
        group_name: str,
        upload_files: list[UploadFile],
        actor: str = "system",
    ) -> TargetGroupUploadResponse:
        if not upload_files:
            raise ValueError("ต้องเลือกไฟล์อย่างน้อย 1 ไฟล์")

        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        stored_files: list[tuple[Path, UploadFile]] = []
        for upload_file in upload_files:
            suffix = Path(upload_file.filename or "group.xlsx").suffix or ".xlsx"
            stored_path = settings.upload_dir / f"{uuid4()}{suffix}"
            with stored_path.open("wb") as handle:
                handle.write(upload_file.file.read())
            stored_files.append((stored_path, upload_file))

        fingerprints = [FileHashService.fingerprint(path) for path, _ in stored_files]
        cls._validate_upload_batch(fingerprints)
        source_set_hash = FileHashService.manifest_hash(fingerprints)

        # Idempotency / duplicate-job guard: if the exact same file *content* was
        # already imported under the same group name, do NOT create a second job.
        # Covers a slow import that made the frontend time out and the user
        # retried — the first job already exists. We key on the set of file
        # CONTENT hashes (sha256), NOT source_set_hash: source_set_hash includes
        # the stored filename/path/mtime, which are unique per upload (files are
        # written to a fresh uuid path each time), so it would never match a
        # retry. Content sha256 is stable across re-uploads of the same file.
        # Matching by (content + group_name) still allows re-using the same
        # roster under a *different* group name.
        new_content_hashes = sorted({fp.sha256 for fp in fingerprints})
        same_name_jobs = db.scalars(
            select(TargetGroupJob)
            .where(TargetGroupJob.group_name == group_name)
            .order_by(desc(TargetGroupJob.created_at))
        ).all()
        for candidate in same_name_jobs:
            candidate_hashes = sorted(
                set(
                    db.scalars(
                        select(TargetGroupJobFile.sha256).where(
                            TargetGroupJobFile.group_job_id == candidate.id
                        )
                    ).all()
                )
            )
            if candidate_hashes and candidate_hashes == new_content_hashes:
                logger.info(
                    "target_group.upload.duplicate_skipped group_id=%s status=%s",
                    candidate.id,
                    candidate.parse_status,
                )
                raise DuplicateUploadError(group_id=candidate.id, parse_status=candidate.parse_status)

        summary = TargetGroupImportSummary(total_uploaded_files=len(stored_files))

        job = TargetGroupJob(
            group_name=group_name,
            source_file_name=stored_files[0][1].filename or stored_files[0][0].name,
            source_file_type=detect_file_type(stored_files[0][0]),
            source_file_hash=fingerprints[0].sha256 if len(fingerprints) == 1 else source_set_hash,
            source_set_hash=source_set_hash,
            source_file_count=len(stored_files),
            uploaded_by=actor,
            parse_status="processing",
            match_status="pending",
            notes="TODO: scanned PDF OCR rows stay visible as ต้องตรวจสอบ until manual review support is added.",
        )
        db.add(job)
        db.flush()
        AuditLogService.create_event(
            db,
            actor=actor,
            action="upload_target_group_files",
            entity_type="target_group_jobs",
            entity_id=str(job.id),
            status="started",
            context={
                "group_name": group_name,
                "source_file_count": len(stored_files),
                "source_set_hash": source_set_hash,
            },
        )
        db.flush()

        issues: list[ValidationIssue] = []
        preview_rows: list[TargetGroupPreviewRow] = []
        uploaded_files: list[SourceFileResponse] = []
        uploaded_sheets = []

        try:
            for (stored_path, upload_file), fingerprint in zip(stored_files, fingerprints, strict=True):
                file_type = detect_file_type(stored_path)
                job_file = TargetGroupJobFile(
                    group_job_id=job.id,
                    file_name=upload_file.filename or stored_path.name,
                    file_path=str(stored_path.resolve()),
                    file_type=file_type,
                    sha256=fingerprint.sha256,
                    size_bytes=fingerprint.size_bytes,
                    source_modified_at=fingerprint.modified_at,
                    parse_status="processing",
                )
                db.add(job_file)
                db.flush()

                workbook = cls._read_target_group_workbook(stored_path, file_type)
                sheet_lookup = cls._persist_sheet_metadata(db, job.id, job_file, workbook.sheets)
                file_summary, file_issues = cls._stage_rows(
                    db=db,
                    job=job,
                    job_file=job_file,
                    rows=workbook.rows,
                    sheet_lookup=sheet_lookup,
                    preview_rows=preview_rows,
                )
                cls._merge_summary(summary, file_summary)
                issues.extend(file_issues)

                job_file.row_count = len(workbook.rows)
                job_file.warning_count = file_summary.warning_rows
                job_file.parse_status = (
                    "parse_failed" if file_summary.failed_rows == len(workbook.rows) and len(workbook.rows) else "parsed"
                )
                if file_summary.warning_rows or file_summary.invalid_cid_rows:
                    job_file.parse_status = "warning"
                job_file.error_message = file_issues[0].message if file_issues else None
                job_file.parse_error_summary = cls._build_parse_error_summary(file_summary)
                db.add(job_file)

                uploaded_files.append(
                    SourceFileResponse(
                        file_id=job_file.id,
                        file_name=job_file.file_name,
                        file_path=job_file.file_path,
                        file_type=job_file.file_type,
                        sha256=job_file.sha256,
                        size_bytes=job_file.size_bytes or 0,
                        modified_at=job_file.source_modified_at,
                        parse_status=job_file.parse_status,
                        row_count=job_file.row_count,
                        warning_count=job_file.warning_count,
                        error_message=job_file.error_message,
                        parse_error_summary=job_file.parse_error_summary,
                    )
                )
                uploaded_sheets.extend(cls._build_sheet_responses_from_lookup(sheet_lookup))

            duplicate_issues = cls._apply_duplicate_cid_statuses(db, job.id)
            issues.extend(duplicate_issues)
            summary = cls._recompute_summary_from_rows(
                db.scalars(select(TargetGroupRow).where(TargetGroupRow.group_job_id == job.id)).all(),
                total_uploaded_files=len(stored_files),
            )

            cls._persist_job_summary(job, summary)
            job.parse_status = "warning" if summary.warning_rows or summary.invalid_cid_rows or summary.missing_cid_rows else "success"
            db.add(job)
            AuditLogService.create_event(
                db,
                actor=actor,
                action="upload_target_group_files",
                entity_type="target_group_jobs",
                entity_id=str(job.id),
                status="success",
                context={
                    "group_name": group_name,
                    "source_file_count": len(stored_files),
                    "summary": summary.__dict__,
                    "source_set_hash": source_set_hash,
                },
            )
            db.commit()
            db.refresh(job)

            logger.info(
                "target_group.upload group_id=%s file_count=%s total_rows=%s valid=%s invalid=%s duplicate=%s warning=%s",
                job.id,
                len(stored_files),
                summary.total_rows,
                summary.valid_cid_rows,
                summary.invalid_cid_rows + summary.missing_cid_rows,
                summary.duplicate_cid_rows,
                summary.warning_rows,
            )

            return TargetGroupUploadResponse(
                group_id=job.id,
                group_name=job.group_name,
                parse_status=job.parse_status,
                source_file_count=job.source_file_count,
                total_rows=summary.total_rows,
                import_summary=summary.to_response(),
                uploaded_files=uploaded_files,
                sheets=uploaded_sheets,
                preview_rows=preview_rows,
                validation_issues=issues[:50],
                uploaded_at=job.created_at,
            )
        except Exception as exc:
            db.rollback()
            persisted_job = db.get(TargetGroupJob, job.id)
            if persisted_job is not None:
                persisted_job.parse_status = "failed"
                db.add(persisted_job)
                AuditLogService.create_event(
                    db,
                    actor=actor,
                    action="upload_target_group_files",
                    entity_type="target_group_jobs",
                    entity_id=str(job.id),
                    status="failed",
                    context={
                        "group_name": group_name,
                        "source_file_count": len(stored_files),
                        "source_set_hash": source_set_hash,
                    },
                    error_summary=str(exc),
                )
                db.commit()
            raise

    @staticmethod
    def confirm_import(db: Session, group_id: UUID) -> ConfirmImportResponse:
        job = db.get(TargetGroupJob, group_id)
        if job is None:
            raise ValueError("ไม่พบกลุ่มเป้าหมาย")
        if job.parse_status == "processing":
            raise ValueError("งานนำเข้ายังประมวลผลไม่เสร็จ")
        if job.parse_status == "failed":
            raise ValueError("งานนำเข้าไม่สำเร็จ จึงยังยืนยันไม่ได้")
        job.parse_status = "success" if job.parse_status != "warning" else "warning"
        db.add(job)
        db.commit()
        return ConfirmImportResponse(group_id=job.id, parse_status=job.parse_status, match_status=job.match_status)

    @staticmethod
    def _validate_upload_batch(fingerprints) -> None:
        duplicate_names = sorted(
            {
                item.filename
                for item in fingerprints
                if sum(1 for other in fingerprints if other.sha256 == item.sha256) > 1
            }
        )
        if duplicate_names:
            raise ValueError(
                f"พบไฟล์ซ้ำในชุดอัปโหลดเดียวกัน: {', '.join(duplicate_names)} กรุณาตรวจสอบก่อนอัปโหลดใหม่"
            )

    @staticmethod
    def list_groups(db: Session, limit: int = 20) -> list[TargetGroupListItemResponse]:
        jobs = db.scalars(select(TargetGroupJob).order_by(desc(TargetGroupJob.created_at)).limit(limit)).all()
        return [TargetGroupImportService._build_list_item(db, job) for job in jobs]

    @staticmethod
    def get_group_detail(db: Session, group_id: UUID) -> TargetGroupDetailResponse:
        job = db.get(TargetGroupJob, group_id)
        if job is None:
            raise ValueError("ไม่พบกลุ่มเป้าหมาย")
        return TargetGroupImportService._build_detail(db, job)

    @staticmethod
    def update_group_name(db: Session, group_id: UUID, group_name: str) -> "TargetGroupDetailResponse":
        job = db.get(TargetGroupJob, group_id)
        if job is None:
            raise ValueError("ไม่พบกลุ่มเป้าหมาย")
        job.group_name = group_name.strip()
        db.commit()
        db.refresh(job)
        return TargetGroupImportService.get_group_detail(db, group_id)

    @classmethod
    def add_files_to_group(
        cls,
        db: Session,
        group_id: UUID,
        upload_files: list[UploadFile],
        actor: str = "system",
    ) -> TargetGroupDetailResponse:
        """Attach new files to an existing TargetGroupJob without creating a new group.

        Safety rules:
        - Rejects files whose SHA-256 already exists in the job (exact duplicate).
        - Rejects any two new files that are identical to each other.
        - After adding rows, re-runs _apply_duplicate_cid_statuses across ALL rows.
        - Recomputes source_set_hash from all files, marks match_status="pending"
          and clears result summaries so stale-detection kicks in on the frontend.
        """
        if not upload_files:
            raise ValueError("ต้องเลือกไฟล์อย่างน้อย 1 ไฟล์")

        job = db.get(TargetGroupJob, group_id)
        if job is None:
            raise ValueError("ไม่พบกลุ่มเป้าหมาย")

        settings.upload_dir.mkdir(parents=True, exist_ok=True)

        # Store files to disk and compute fingerprints
        stored_files: list[tuple[Path, UploadFile]] = []
        for upload_file in upload_files:
            suffix = Path(upload_file.filename or "group.xlsx").suffix or ".xlsx"
            stored_path = settings.upload_dir / f"{uuid4()}{suffix}"
            with stored_path.open("wb") as handle:
                handle.write(upload_file.file.read())
            stored_files.append((stored_path, upload_file))

        new_fingerprints = [FileHashService.fingerprint(path) for path, _ in stored_files]

        # Validate: no duplicates within the new batch
        cls._validate_upload_batch(new_fingerprints)

        # Validate: no duplicates against files already in this job
        existing_files = db.scalars(
            select(TargetGroupJobFile).where(TargetGroupJobFile.group_job_id == group_id)
        ).all()
        existing_hashes = {f.sha256 for f in existing_files}
        duplicate_against_existing = [
            fp.filename for fp in new_fingerprints if fp.sha256 in existing_hashes
        ]
        if duplicate_against_existing:
            raise ValueError(
                f"ไฟล์ต่อไปนี้มีอยู่ในกลุ่มนี้แล้ว: {', '.join(duplicate_against_existing)} "
                "กรุณาเลือกไฟล์ที่แตกต่างกัน"
            )

        AuditLogService.create_event(
            db,
            actor=actor,
            action="add_files_to_group",
            entity_type="target_group_jobs",
            entity_id=str(job.id),
            status="started",
            context={
                "group_name": job.group_name,
                "new_file_count": len(stored_files),
            },
        )
        db.flush()

        summary = TargetGroupImportSummary(total_uploaded_files=len(stored_files))
        issues: list[ValidationIssue] = []
        preview_rows: list[TargetGroupPreviewRow] = []

        try:
            for (stored_path, upload_file), fingerprint in zip(stored_files, new_fingerprints, strict=True):
                file_type = detect_file_type(stored_path)
                job_file = TargetGroupJobFile(
                    group_job_id=job.id,
                    file_name=upload_file.filename or stored_path.name,
                    file_path=str(stored_path.resolve()),
                    file_type=file_type,
                    sha256=fingerprint.sha256,
                    size_bytes=fingerprint.size_bytes,
                    source_modified_at=fingerprint.modified_at,
                    parse_status="processing",
                )
                db.add(job_file)
                db.flush()

                workbook = cls._read_target_group_workbook(stored_path, file_type)
                sheet_lookup = cls._persist_sheet_metadata(db, job.id, job_file, workbook.sheets)
                file_summary, file_issues = cls._stage_rows(
                    db=db,
                    job=job,
                    job_file=job_file,
                    rows=workbook.rows,
                    sheet_lookup=sheet_lookup,
                    preview_rows=preview_rows,
                )
                cls._merge_summary(summary, file_summary)
                issues.extend(file_issues)

                job_file.row_count = len(workbook.rows)
                job_file.warning_count = file_summary.warning_rows
                job_file.parse_status = (
                    "parse_failed"
                    if file_summary.failed_rows == len(workbook.rows) and len(workbook.rows)
                    else "parsed"
                )
                if file_summary.warning_rows or file_summary.invalid_cid_rows:
                    job_file.parse_status = "warning"
                job_file.error_message = file_issues[0].message if file_issues else None
                job_file.parse_error_summary = cls._build_parse_error_summary(file_summary)
                db.add(job_file)

            # Re-run duplicate CID detection across ALL rows (old + new)
            duplicate_issues = cls._apply_duplicate_cid_statuses(db, job.id)
            issues.extend(duplicate_issues)

            # Recompute summary counts from all rows
            all_rows = db.scalars(
                select(TargetGroupRow).where(TargetGroupRow.group_job_id == job.id)
            ).all()
            full_summary = cls._recompute_summary_from_rows(
                all_rows,
                total_uploaded_files=len(existing_files) + len(stored_files),
            )

            # Recompute source_set_hash from all files (old + new)
            all_file_records = db.scalars(
                select(TargetGroupJobFile)
                .where(TargetGroupJobFile.group_job_id == job.id)
                .order_by(TargetGroupJobFile.created_at.asc())
            ).all()
            all_fingerprints = [FileHashService.fingerprint(Path(f.file_path)) for f in all_file_records]
            new_source_set_hash = FileHashService.manifest_hash(all_fingerprints)

            # Update job metadata
            cls._persist_job_summary(job, full_summary)
            job.source_set_hash = new_source_set_hash
            job.source_file_count = len(all_file_records)
            # Keep source_file_name pointing to the first file (original)
            job.source_file_hash = (
                all_fingerprints[0].sha256 if len(all_fingerprints) == 1 else new_source_set_hash
            )
            # Reset match so user re-runs match with new data
            job.match_status = "pending"
            job.parse_status = (
                "warning"
                if full_summary.warning_rows or full_summary.invalid_cid_rows or full_summary.missing_cid_rows
                else "success"
            )
            db.add(job)

            AuditLogService.create_event(
                db,
                actor=actor,
                action="add_files_to_group",
                entity_type="target_group_jobs",
                entity_id=str(job.id),
                status="success",
                context={
                    "group_name": job.group_name,
                    "new_file_count": len(stored_files),
                    "total_file_count": len(all_file_records),
                    "new_source_set_hash": new_source_set_hash,
                    "summary": full_summary.__dict__,
                },
            )
            db.commit()
            db.refresh(job)

            logger.info(
                "target_group.add_files group_id=%s new_files=%s total_files=%s total_rows=%s",
                job.id,
                len(stored_files),
                len(all_file_records),
                full_summary.total_rows,
            )
            return cls._build_detail(db, job)

        except Exception as exc:
            db.rollback()
            AuditLogService.create_event(
                db,
                actor=actor,
                action="add_files_to_group",
                entity_type="target_group_jobs",
                entity_id=str(job.id),
                status="failed",
                context={"group_name": job.group_name, "new_file_count": len(stored_files)},
                error_summary=str(exc),
            )
            db.commit()
            raise

    @staticmethod
    def get_group_files(db: Session, group_id: UUID) -> list[SourceFileResponse]:
        job = db.get(TargetGroupJob, group_id)
        if job is None:
            raise ValueError("ไม่พบกลุ่มเป้าหมาย")
        return TargetGroupImportService._list_uploaded_files(db, group_id)

    @staticmethod
    def get_validation_summary(db: Session, group_id: UUID) -> TargetGroupValidationSummaryResponse:
        job = db.get(TargetGroupJob, group_id)
        if job is None:
            raise ValueError("ไม่พบกลุ่มเป้าหมาย")
        validation_issues = [
            ValidationIssue(
                row_id=row.id,
                row_no=row.row_no,
                source_file_id=row.source_file_id,
                source_file_name=row.source_file_name,
                source_row_no=row.source_row_no,
                field="row",
                message=row.error_message or row.warning_message or "ต้องตรวจสอบ",
            )
            for row in db.scalars(
                select(TargetGroupRow)
                .where(
                    TargetGroupRow.group_job_id == job.id,
                    (TargetGroupRow.error_message.is_not(None)) | (TargetGroupRow.warning_message.is_not(None)),
                )
                .order_by(TargetGroupRow.row_no.asc())
                .limit(50)
            ).all()
        ]
        return TargetGroupValidationSummaryResponse(
            group_id=job.id,
            total_rows=job.total_rows,
            invalid_rows=job.invalid_rows,
            missing_cid_rows=job.missing_cid_rows,
            duplicate_cid_rows=job.duplicate_cid_rows,
            review_required_rows=job.invalid_rows + job.warning_rows,
            validation_issues=validation_issues,
        )

    @staticmethod
    def disease_options(db: Session) -> list[DiseaseOptionResponse]:
        mapping_rows = db.scalars(
            select(DiseaseMapping).where(DiseaseMapping.is_active.is_(True)).order_by(DiseaseMapping.normalized_label.asc())
        ).all()
        distinct_by_key: dict[str, DiseaseMapping] = {}
        for row in mapping_rows:
            distinct_by_key.setdefault(row.normalized_key, row)
        return [
            DiseaseOptionResponse(
                key=row.normalized_key,
                label=row.normalized_label,
                icd10_code=row.icd10_code,
                raw_name=row.raw_name,
            )
            for row in distinct_by_key.values()
        ]

    @staticmethod
    def _read_target_group_workbook(stored_path: Path, file_type: str) -> ParsedTargetGroupWorkbook:
        if file_type == "pdf":
            rows = PdfTargetGroupImporter.read_rows(stored_path)
            return ParsedTargetGroupWorkbook(rows=rows, sheets=[])
        return ExcelTargetGroupImporter.read_workbook(stored_path)

    @staticmethod
    def _persist_sheet_metadata(
        db: Session,
        group_job_id: UUID,
        job_file: TargetGroupJobFile,
        sheets: list[ParsedTargetGroupSheet],
    ) -> dict[tuple[int, str], TargetGroupSheet]:
        persisted: dict[tuple[int, str], TargetGroupSheet] = {}
        for parsed_sheet in sheets:
            sheet = TargetGroupSheet(
                group_job_id=group_job_id,
                source_file_id=job_file.id,
                sheet_name=parsed_sheet.sheet_name,
                sheet_index=parsed_sheet.sheet_index,
                sheet_type=parsed_sheet.sheet_type,
                row_count=parsed_sheet.row_count,
                column_names_json=parsed_sheet.column_names,
                classification_confidence=parsed_sheet.classification_confidence,
                notes=parsed_sheet.notes,
            )
            db.add(sheet)
            db.flush()
            persisted[(parsed_sheet.sheet_index, parsed_sheet.sheet_name)] = sheet
        return persisted

    @staticmethod
    def _build_sheet_responses_from_lookup(sheet_lookup: dict[tuple[int, str], TargetGroupSheet]) -> list:
        from app.schemas.target_group import TargetGroupSheetResponse

        return [
            TargetGroupSheetResponse(
                sheet_id=sheet.id,
                source_file_id=sheet.source_file_id,
                sheet_name=sheet.sheet_name,
                sheet_index=sheet.sheet_index,
                sheet_type=sheet.sheet_type,
                row_count=sheet.row_count,
                column_names=sheet.column_names_json or [],
                classification_confidence=float(sheet.classification_confidence)
                if sheet.classification_confidence is not None
                else None,
                notes=sheet.notes,
            )
            for sheet in sorted(sheet_lookup.values(), key=lambda item: (item.sheet_index, item.sheet_name.casefold()))
        ]

    @classmethod
    def _stage_rows(
        cls,
        db: Session,
        job: TargetGroupJob,
        job_file: TargetGroupJobFile,
        rows: list[ParsedTargetGroupRow],
        sheet_lookup: dict[tuple[int, str], TargetGroupSheet],
        preview_rows: list[TargetGroupPreviewRow],
    ) -> tuple[TargetGroupImportSummary, list[ValidationIssue]]:
        issues: list[ValidationIssue] = []
        summary = TargetGroupImportSummary(total_rows=0, parsed_rows=0)
        sheet_warnings_seen: set[tuple[str, str | None]] = set()
        for parsed in rows:
            source_sheet = sheet_lookup.get((parsed.source_sheet_index, parsed.source_sheet_name))
            if parsed.sheet_type in {HISTORY_SHEET, MIXED_SHEET}:
                history_issues = cls._stage_history_row(db, job, job_file, parsed, source_sheet)
                issues.extend(history_issues)
                if parsed.sheet_warning:
                    summary.warning_rows += 1
                if parsed.sheet_type == HISTORY_SHEET:
                    continue

            if parsed.sheet_type not in {ROSTER_SHEET, MIXED_SHEET}:
                # Emit one sheet-level ValidationIssue so the upload response
                # surfaces the classification warning to the caller.
                warning_key = (parsed.source_sheet_name, parsed.sheet_warning)
                if parsed.sheet_warning and warning_key not in sheet_warnings_seen:
                    issues.append(
                        ValidationIssue(
                            row_id=None,
                            row_no=parsed.row_number,
                            source_file_id=job_file.id,
                            source_file_name=parsed.source_filename,
                            source_row_no=parsed.row_number,
                            field="sheet_type",
                            message=parsed.sheet_warning,
                        )
                    )
                    sheet_warnings_seen.add(warning_key)
                    summary.warning_rows += 1

                # For UNKNOWN_SHEET rows that carry at least one person-identity
                # value, attempt to stage them as TargetGroupHistoryRow with
                # validation_status="unclassified".  This preserves potentially
                # useful history evidence for later review instead of discarding
                # the row permanently.  Rows with no identifiable person fields
                # are skipped (truly uninterpretable content).
                if parsed.sheet_type == UNKNOWN_SHEET:
                    payload_keys_lower = {str(k).strip().casefold() for k in parsed.values}
                    identity_hint_cols = {c.casefold() for c in PERSON_IDENTITY_COLUMNS}
                    has_identity_column = bool(payload_keys_lower & identity_hint_cols)
                    has_identity_value = any(
                        v for k, v in parsed.values.items()
                        if str(k).strip().casefold() in identity_hint_cols and v
                    )
                    if has_identity_column and has_identity_value:
                        cls._stage_unknown_sheet_row(db, job, job_file, parsed, source_sheet)

                continue

            payload = parsed.values
            summary.total_rows += 1
            summary.parsed_rows += 1
            normalized, row_issues = StagingValidationService.validate_target_group_row(parsed.row_number, payload)
            parse_warning = payload.get("parse_warning")
            if parse_warning:
                row_issues = [
                    *row_issues,
                    ValidationIssue(
                        row_id=None,
                        row_no=parsed.row_number,
                        source_file_id=job_file.id,
                        source_file_name=parsed.source_filename,
                        source_row_no=parsed.row_number,
                        field="parse",
                        message=str(parse_warning),
                    ),
                ]
            contextual_issues = [
                ValidationIssue(
                    row_id=None,
                    row_no=issue.row_no,
                    source_file_id=job_file.id,
                    source_file_name=parsed.source_filename,
                    source_row_no=parsed.row_number,
                    field=issue.field,
                    message=f"[{parsed.source_filename}] {issue.message}",
                )
                for issue in row_issues
            ]

            validation_status = "invalid" if contextual_issues else "valid"
            warning_message = None
            if normalized["cid_validation_status"] == "missing_identifier":
                summary.missing_cid_rows += 1
            elif normalized["cid_validation_status"] == "invalid_identifier":
                summary.invalid_cid_rows += 1
            else:
                summary.valid_cid_rows += 1

            if parse_warning and validation_status == "valid":
                validation_status = "warning"
                warning_message = f"[{parsed.source_filename}] {parse_warning}"
                summary.warning_rows += 1

            if contextual_issues:
                summary.failed_rows += 1 if parse_warning else 0
                if normalized["cid_validation_status"] not in {"invalid_identifier", "missing_identifier"}:
                    summary.invalid_cid_rows += 1
                    summary.valid_cid_rows = max(summary.valid_cid_rows - 1, 0)

            issues.extend(contextual_issues)
            db.add(
                TargetGroupRow(
                    group_job_id=job.id,
                    source_file_id=job_file.id,
                    source_file_name=job_file.file_name,
                    source_row_no=parsed.row_number,
                    row_no=parsed.row_number,
                    raw_cid=normalized["raw_cid"],
                    raw_pid=payload.get("pid") or payload.get("PID"),
                    raw_citizen_id=payload.get("citizen_id") or payload.get("cid") or payload.get("CID"),
                    raw_hn=normalized["raw_hn"],
                    raw_full_name=normalized["raw_full_name"],
                    raw_birth_date=normalized["raw_birth_date"],
                    raw_age=normalized["raw_age"],
                    raw_sex=normalized["raw_sex"],
                    raw_target_history_labels=normalized["raw_target_history_labels"],
                    raw_target_history_note=normalized["raw_target_history_note"],
                    raw_target_history_last_visit_date=normalized["raw_target_history_last_visit_date"],
                    normalized_cid=normalized["normalized_cid"],
                    normalized_pid=None,
                    normalized_citizen_id=normalized["normalized_citizen_id"],
                    normalized_hn=normalized["normalized_hn"],
                    normalized_full_name=normalized["normalized_full_name"],
                    normalized_birth_date=normalized["normalized_birth_date"],
                    normalized_age=normalized["normalized_age"],
                    normalized_sex=normalized["normalized_sex"],
                    normalized_target_history_service_keys=normalized["normalized_target_history_service_keys"],
                    normalized_target_history_last_visit_date=normalized["normalized_target_history_last_visit_date"],
                    parse_status="parse_failed" if parse_warning else "parsed",
                    validation_status=validation_status,
                    cid_validation_status=normalized["cid_validation_status"],
                    duplicate_status="unique_in_job",
                    match_status="pending",
                    match_method=None,
                    confidence_flag="medium" if validation_status != "invalid" else "low",
                    matched_identifier_basis=None,
                    matched_name_basis=None,
                    error_message="; ".join(issue.message for issue in contextual_issues) or None,
                    warning_message=warning_message,
                    raw_json={
                        **payload,
                        "source_filename": parsed.source_filename,
                        "source_sheet_name": parsed.source_sheet_name,
                        "source_sheet_index": parsed.source_sheet_index,
                        "source_row_number": parsed.row_number,
                        "sheet_type": parsed.sheet_type,
                    },
                )
            )
            cls._stage_embedded_history_from_roster_row(
                db=db,
                job=job,
                job_file=job_file,
                parsed=parsed,
                source_sheet=source_sheet,
                normalized_row=normalized,
            )
            if len(preview_rows) < 10:
                preview_rows.append(
                    TargetGroupPreviewRow(
                        row_id=None,
                        row_no=parsed.row_number,
                        source_file_id=job_file.id,
                        source_file_name=parsed.source_filename,
                        source_row_no=parsed.row_number,
                        normalized_cid=normalized["normalized_cid"],
                        parse_status="parse_failed" if parse_warning else "parsed",
                        values=payload,
                    )
                )
        db.flush()
        return summary, issues

    @classmethod
    def _stage_history_row(
        cls,
        db: Session,
        job: TargetGroupJob,
        job_file: TargetGroupJobFile,
        parsed: ParsedTargetGroupRow,
        source_sheet: TargetGroupSheet | None,
    ) -> list[ValidationIssue]:
        payload = parsed.values
        normalized, row_issues = StagingValidationService.validate_target_group_history_row(parsed.row_number, payload)
        issues = [
            ValidationIssue(
                row_id=None,
                row_no=issue.row_no,
                source_file_id=job_file.id,
                source_file_name=parsed.source_filename,
                source_row_no=parsed.row_number,
                field=issue.field,
                message=f"[{parsed.source_filename}/{parsed.source_sheet_name}] {issue.message}",
            )
            for issue in row_issues
        ]
        validation_status = "invalid" if issues else "valid"
        warning_parts = [parsed.sheet_warning, normalized["warning_message"]]
        warning_message = "; ".join(part for part in warning_parts if part) or None
        if warning_message and validation_status == "valid":
            validation_status = "warning"

        db.add(
            TargetGroupHistoryRow(
                group_job_id=job.id,
                source_file_id=job_file.id,
                source_sheet_id=source_sheet.id if source_sheet else None,
                source_file_name=job_file.file_name,
                source_sheet_name=parsed.source_sheet_name,
                source_row_no=parsed.row_number,
                raw_cid=normalized["raw_cid"],
                normalized_cid=normalized["normalized_cid"],
                raw_full_name=normalized["raw_full_name"],
                normalized_full_name=normalized["normalized_full_name"],
                raw_birth_date=normalized["raw_birth_date"],
                normalized_birth_date=normalized["normalized_birth_date"],
                raw_address=normalized["raw_address"],
                normalized_address=normalized["normalized_address"],
                raw_service_label=normalized["raw_service_label"],
                raw_service_type=normalized["raw_service_type"],
                normalized_service_key=normalized["normalized_service_key"],
                raw_visit_date=normalized["raw_visit_date"],
                normalized_visit_date=normalized["normalized_visit_date"],
                raw_icd10=normalized["raw_icd10"],
                raw_result=normalized["raw_result"],
                raw_hpv=normalized["raw_hpv"],
                raw_hospital=normalized["raw_hospital"],
                raw_doctor=normalized["raw_doctor"],
                raw_note=normalized["raw_note"],
                parse_status="parsed",
                validation_status=validation_status,
                identifier_validation_status=normalized["identifier_validation_status"],
                date_validation_status=normalized["date_validation_status"],
                service_validation_status=normalized["service_validation_status"],
                warning_message=warning_message,
                raw_json={
                    **payload,
                    "source_filename": parsed.source_filename,
                    "source_sheet_name": parsed.source_sheet_name,
                    "source_sheet_index": parsed.source_sheet_index,
                    "source_row_number": parsed.row_number,
                    "sheet_type": parsed.sheet_type,
                },
            )
        )
        return issues

    @classmethod
    def _stage_embedded_history_from_roster_row(
        cls,
        db: Session,
        job: TargetGroupJob,
        job_file: TargetGroupJobFile,
        parsed: ParsedTargetGroupRow,
        source_sheet: TargetGroupSheet | None,
        normalized_row: dict,
    ) -> None:
        if parsed.sheet_type == MIXED_SHEET:
            return

        has_embedded_history = bool(
            normalized_row.get("normalized_target_history_service_keys")
            and normalized_row.get("normalized_target_history_last_visit_date")
        )
        if not has_embedded_history:
            return

        payload = parsed.values
        normalized_history, row_issues = StagingValidationService.validate_target_group_history_row(parsed.row_number, payload)
        if row_issues:
            logger.warning(
                "target_group.embedded_history_skipped group_id=%s file=%s sheet=%s row=%s issues=%s",
                job.id,
                parsed.source_filename,
                parsed.source_sheet_name,
                parsed.row_number,
                [issue.message for issue in row_issues],
            )
            return

        warning_parts = [parsed.sheet_warning, normalized_history["warning_message"], "derived_from_roster_row"]
        warning_message = "; ".join(part for part in warning_parts if part) or None

        db.add(
            TargetGroupHistoryRow(
                group_job_id=job.id,
                source_file_id=job_file.id,
                source_sheet_id=source_sheet.id if source_sheet else None,
                source_file_name=job_file.file_name,
                source_sheet_name=parsed.source_sheet_name,
                source_row_no=parsed.row_number,
                raw_cid=normalized_history["raw_cid"],
                normalized_cid=normalized_history["normalized_cid"],
                raw_full_name=normalized_history["raw_full_name"],
                normalized_full_name=normalized_history["normalized_full_name"],
                raw_birth_date=normalized_history["raw_birth_date"],
                normalized_birth_date=normalized_history["normalized_birth_date"],
                raw_address=normalized_history["raw_address"],
                normalized_address=normalized_history["normalized_address"],
                raw_service_label=normalized_history["raw_service_label"],
                raw_service_type=normalized_history["raw_service_type"],
                normalized_service_key=normalized_history["normalized_service_key"],
                raw_visit_date=normalized_history["raw_visit_date"],
                normalized_visit_date=normalized_history["normalized_visit_date"],
                raw_icd10=normalized_history["raw_icd10"],
                raw_result=normalized_history["raw_result"],
                raw_hpv=normalized_history["raw_hpv"],
                raw_hospital=normalized_history["raw_hospital"],
                raw_doctor=normalized_history["raw_doctor"],
                raw_note=normalized_history["raw_note"],
                parse_status="parsed",
                validation_status="warning" if warning_message else "valid",
                identifier_validation_status=normalized_history["identifier_validation_status"],
                date_validation_status=normalized_history["date_validation_status"],
                service_validation_status=normalized_history["service_validation_status"],
                warning_message=warning_message,
                raw_json={
                    **payload,
                    "source_filename": parsed.source_filename,
                    "source_sheet_name": parsed.source_sheet_name,
                    "source_sheet_index": parsed.source_sheet_index,
                    "source_row_number": parsed.row_number,
                    "sheet_type": parsed.sheet_type,
                    "derived_from_roster_row": True,
                },
            )
        )

    @classmethod
    def _stage_unknown_sheet_row(
        cls,
        db: Session,
        job: TargetGroupJob,
        job_file: TargetGroupJobFile,
        parsed: ParsedTargetGroupRow,
        source_sheet: TargetGroupSheet | None,
    ) -> None:
        """Stage a row from an UNKNOWN_SHEET classification as an unclassified history row.

        Only called when the row has at least one identity column with a non-empty value.
        The row is staged with validation_status="unclassified" so it remains visible and
        reviewable rather than being silently dropped.
        """
        payload = parsed.values
        normalized_history, row_issues = StagingValidationService.validate_target_group_history_row(
            parsed.row_number, payload
        )

        sheet_note = "unclassified_sheet"
        warning_parts = [
            parsed.sheet_warning,
            normalized_history.get("warning_message"),
            sheet_note,
        ]
        warning_message = "; ".join(part for part in warning_parts if part) or sheet_note

        db.add(
            TargetGroupHistoryRow(
                group_job_id=job.id,
                source_file_id=job_file.id,
                source_sheet_id=source_sheet.id if source_sheet else None,
                source_file_name=job_file.file_name,
                source_sheet_name=parsed.source_sheet_name,
                source_row_no=parsed.row_number,
                raw_cid=normalized_history.get("raw_cid"),
                normalized_cid=normalized_history.get("normalized_cid"),
                raw_full_name=normalized_history.get("raw_full_name"),
                normalized_full_name=normalized_history.get("normalized_full_name"),
                raw_birth_date=normalized_history.get("raw_birth_date"),
                normalized_birth_date=normalized_history.get("normalized_birth_date"),
                raw_address=normalized_history.get("raw_address"),
                normalized_address=normalized_history.get("normalized_address"),
                raw_service_label=normalized_history.get("raw_service_label"),
                raw_service_type=normalized_history.get("raw_service_type"),
                normalized_service_key=normalized_history.get("normalized_service_key"),
                raw_visit_date=normalized_history.get("raw_visit_date"),
                normalized_visit_date=normalized_history.get("normalized_visit_date"),
                raw_icd10=normalized_history.get("raw_icd10"),
                raw_result=normalized_history.get("raw_result"),
                raw_hpv=normalized_history.get("raw_hpv"),
                raw_hospital=normalized_history.get("raw_hospital"),
                raw_doctor=normalized_history.get("raw_doctor"),
                raw_note=normalized_history.get("raw_note"),
                parse_status="parsed",
                validation_status="unclassified",
                identifier_validation_status=normalized_history.get("identifier_validation_status"),
                date_validation_status=normalized_history.get("date_validation_status"),
                service_validation_status=normalized_history.get("service_validation_status"),
                warning_message=warning_message,
                raw_json={
                    **payload,
                    "source_filename": parsed.source_filename,
                    "source_sheet_name": parsed.source_sheet_name,
                    "source_sheet_index": parsed.source_sheet_index,
                    "source_row_number": parsed.row_number,
                    "sheet_type": parsed.sheet_type,
                    "staged_as_unclassified": True,
                },
            )
        )

    @staticmethod
    def _merge_summary(target: TargetGroupImportSummary, source: TargetGroupImportSummary) -> None:
        target.total_rows += source.total_rows
        target.parsed_rows += source.parsed_rows
        target.valid_cid_rows += source.valid_cid_rows
        target.invalid_cid_rows += source.invalid_cid_rows
        target.missing_cid_rows += source.missing_cid_rows
        target.warning_rows += source.warning_rows
        target.failed_rows += source.failed_rows

    @staticmethod
    def _build_parse_error_summary(summary: TargetGroupImportSummary) -> str | None:
        parts: list[str] = []
        if summary.invalid_cid_rows:
            parts.append(f"CID ไม่ผ่านเกณฑ์ {summary.invalid_cid_rows} แถว")
        if summary.missing_cid_rows:
            parts.append(f"CID หาย {summary.missing_cid_rows} แถว")
        if summary.warning_rows:
            parts.append(f"คำเตือน {summary.warning_rows} แถว")
        if summary.failed_rows:
            parts.append(f"parse failed {summary.failed_rows} แถว")
        return "; ".join(parts) or None

    @staticmethod
    def _apply_duplicate_cid_statuses(db: Session, group_job_id: UUID) -> list[ValidationIssue]:
        rows = db.scalars(
            select(TargetGroupRow)
            .where(TargetGroupRow.group_job_id == group_job_id)
            .order_by(TargetGroupRow.row_no.asc())
        ).all()

        counter = Counter(row.normalized_cid for row in rows if row.normalized_cid)
        issues: list[ValidationIssue] = []
        for row in rows:
            if row.normalized_cid and counter[row.normalized_cid] > 1:
                row.duplicate_status = "duplicate_in_job"
                duplicate_message = f"[{row.source_file_name or 'unknown-file'}] พบ CID ซ้ำภายในกลุ่มเป้าหมายเดียวกัน"
                if row.warning_message:
                    if duplicate_message not in row.warning_message:
                        row.warning_message = f"{row.warning_message}; {duplicate_message}"
                else:
                    row.warning_message = duplicate_message
                if row.validation_status == "valid":
                    row.validation_status = "warning"
                issues.append(
                    ValidationIssue(
                        row_id=row.id,
                        row_no=row.row_no,
                        source_file_id=row.source_file_id,
                        source_file_name=row.source_file_name,
                        source_row_no=row.source_row_no,
                        field="raw_cid",
                        message=duplicate_message,
                    )
                )
            else:
                row.duplicate_status = "unique_in_job"
            db.add(row)
        db.flush()
        return issues

    @staticmethod
    def _persist_job_summary(job: TargetGroupJob, summary: TargetGroupImportSummary) -> None:
        job.total_rows = summary.total_rows
        job.parsed_rows = summary.parsed_rows
        job.valid_rows = summary.valid_cid_rows
        job.invalid_rows = summary.invalid_cid_rows
        job.missing_cid_rows = summary.missing_cid_rows
        job.duplicate_cid_rows = summary.duplicate_cid_rows
        job.warning_rows = summary.warning_rows
        job.failed_rows = summary.failed_rows

    @staticmethod
    def _summarize_rows(rows: list[TargetGroupRow], total_uploaded_files: int) -> TargetGroupImportSummary:
        summary = TargetGroupImportSummary(total_uploaded_files=total_uploaded_files)
        summary.total_rows = len(rows)
        summary.parsed_rows = sum(1 for row in rows if row.parse_status == "parsed")
        summary.failed_rows = sum(1 for row in rows if row.parse_status == "parse_failed")
        summary.warning_rows = sum(1 for row in rows if row.validation_status == "warning")
        summary.invalid_cid_rows = sum(1 for row in rows if row.cid_validation_status == "invalid_identifier")
        summary.missing_cid_rows = sum(1 for row in rows if row.cid_validation_status == "missing_identifier")
        summary.duplicate_cid_rows = sum(1 for row in rows if row.duplicate_status == "duplicate_in_job")
        summary.valid_cid_rows = sum(
            1
            for row in rows
            if row.cid_validation_status == "valid_identifier" and row.duplicate_status != "duplicate_in_job"
        )
        return summary

    @classmethod
    def _recompute_summary_from_rows(cls, rows: list[TargetGroupRow], total_uploaded_files: int) -> TargetGroupImportSummary:
        return cls._summarize_rows(rows, total_uploaded_files=total_uploaded_files)

    @staticmethod
    def _build_import_summary(job: TargetGroupJob) -> TargetGroupImportSummaryResponse:
        return TargetGroupImportSummaryResponse(
            total_uploaded_files=job.source_file_count,
            total_rows=job.total_rows,
            parsed_rows=job.parsed_rows,
            valid_cid_rows=job.valid_rows,
            invalid_cid_rows=job.invalid_rows,
            missing_cid_rows=job.missing_cid_rows,
            duplicate_cid_rows=job.duplicate_cid_rows,
            warning_rows=job.warning_rows,
            failed_rows=job.failed_rows,
        )

    @staticmethod
    def _build_list_item(db: Session, job: TargetGroupJob) -> TargetGroupListItemResponse:
        _, _, match_summary = TargetGroupImportService._collect_group_metrics(db, job.id)
        return TargetGroupListItemResponse(
            group_id=job.id,
            group_name=job.group_name,
            source_file_name=job.source_file_name,
            source_file_type=job.source_file_type,
            source_file_count=job.source_file_count,
            parse_status=job.parse_status,
            match_status=job.match_status,
            total_rows=job.total_rows,
            invalid_rows=job.invalid_rows + job.missing_cid_rows,
            import_summary=TargetGroupImportService._build_import_summary(job),
            match_summary=match_summary,
            uploaded_at=job.created_at,
        )

    @staticmethod
    def _build_detail(db: Session, job: TargetGroupJob) -> TargetGroupDetailResponse:
        _, _, match_summary = TargetGroupImportService._collect_group_metrics(db, job.id)
        preview_rows = [
            TargetGroupPreviewRow(
                row_id=row.id,
                row_no=row.row_no,
                source_file_id=row.source_file_id,
                source_file_name=row.source_file_name,
                source_row_no=row.source_row_no,
                normalized_cid=row.normalized_cid,
                parse_status=row.parse_status,
                values=row.raw_json or {},
            )
            for row in db.scalars(
                select(TargetGroupRow).where(TargetGroupRow.group_job_id == job.id).order_by(TargetGroupRow.row_no.asc()).limit(10)
            ).all()
        ]
        validation_issues = [
            ValidationIssue(
                row_id=row.id,
                row_no=row.row_no,
                source_file_id=row.source_file_id,
                source_file_name=row.source_file_name,
                source_row_no=row.source_row_no,
                field="row",
                message=row.error_message or row.warning_message or "invalid row",
            )
            for row in db.scalars(
                select(TargetGroupRow)
                .where(
                    TargetGroupRow.group_job_id == job.id,
                    (TargetGroupRow.error_message.is_not(None)) | (TargetGroupRow.warning_message.is_not(None)),
                )
                .order_by(TargetGroupRow.row_no.asc())
                .limit(20)
            ).all()
        ]

        return TargetGroupDetailResponse(
            group_id=job.id,
            group_name=job.group_name,
            source_file_name=job.source_file_name,
            source_file_type=job.source_file_type,
            source_file_hash=job.source_file_hash,
            source_set_hash=job.source_set_hash,
            source_file_count=job.source_file_count,
            parse_status=job.parse_status,
            match_status=job.match_status,
            total_rows=job.total_rows,
            invalid_rows=job.invalid_rows + job.missing_cid_rows,
            import_summary=TargetGroupImportService._build_import_summary(job),
            match_summary=match_summary,
            uploaded_files=TargetGroupImportService._list_uploaded_files(db, job.id),
            sheets=TargetGroupImportService._list_group_sheets(db, job.id),
            preview_rows=preview_rows,
            validation_issues=validation_issues,
            uploaded_at=job.created_at,
        )

    @staticmethod
    def _list_uploaded_files(db: Session, group_id: UUID) -> list[SourceFileResponse]:
        return [
            SourceFileResponse(
                file_id=file.id,
                file_name=file.file_name,
                file_path=file.file_path,
                file_type=file.file_type,
                sha256=file.sha256,
                size_bytes=file.size_bytes or 0,
                modified_at=file.source_modified_at,
                parse_status=file.parse_status,
                row_count=file.row_count,
                warning_count=file.warning_count,
                error_message=file.error_message,
                parse_error_summary=file.parse_error_summary,
            )
            for file in db.scalars(
                select(TargetGroupJobFile)
                .where(TargetGroupJobFile.group_job_id == group_id)
                .order_by(TargetGroupJobFile.created_at.asc(), TargetGroupJobFile.file_name.asc())
            ).all()
        ]

    @staticmethod
    def _list_group_sheets(db: Session, group_id: UUID) -> list:
        from app.schemas.target_group import TargetGroupSheetResponse

        sheets = db.scalars(
            select(TargetGroupSheet)
            .where(TargetGroupSheet.group_job_id == group_id)
            .order_by(TargetGroupSheet.sheet_index.asc(), TargetGroupSheet.sheet_name.asc())
        ).all()
        return [
            TargetGroupSheetResponse(
                sheet_id=sheet.id,
                source_file_id=sheet.source_file_id,
                sheet_name=sheet.sheet_name,
                sheet_index=sheet.sheet_index,
                sheet_type=sheet.sheet_type,
                row_count=sheet.row_count,
                column_names=sheet.column_names_json or [],
                classification_confidence=float(sheet.classification_confidence)
                if sheet.classification_confidence is not None
                else None,
                notes=sheet.notes,
            )
            for sheet in sheets
        ]

    @staticmethod
    def _collect_group_metrics(db: Session, group_id: UUID) -> tuple[int, int, MatchSummaryResponse]:
        total_rows = db.scalar(
            select(func.count()).select_from(TargetGroupRow).where(TargetGroupRow.group_job_id == group_id)
        ) or 0
        invalid_rows = db.scalar(
            select(func.count()).select_from(TargetGroupRow).where(
                TargetGroupRow.group_job_id == group_id,
                TargetGroupRow.validation_status == "invalid",
            )
        ) or 0
        counts = {status: 0 for status in ("matched", "not_found", "ambiguous", "needs_review", "pending")}
        for status, count in db.execute(
            select(TargetGroupRow.match_status, func.count())
            .where(TargetGroupRow.group_job_id == group_id)
            .group_by(TargetGroupRow.match_status)
        ).all():
            counts[status or "pending"] = count
        return total_rows, invalid_rows, MatchSummaryResponse(**counts)
