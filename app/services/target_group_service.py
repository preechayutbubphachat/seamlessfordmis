from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.importers.excel_importer import ExcelImporter
from app.models.target_group import ParseStatus, TargetGroupJob, TargetGroupRow, TargetGroupStatus
from app.schemas.common import AuditLogCreate, ValidationIssue
from app.schemas.imports import ConfirmTargetGroupResponse, TargetGroupJobResponse, TargetGroupUploadResponse
from app.services.audit_service import AuditService
from app.services.file_hash_service import FileHashService
from app.services.validation_service import ValidationService


class TargetGroupService:
    @staticmethod
    def get_job(db: Session, job_id: int) -> TargetGroupJobResponse:
        job = db.scalar(select(TargetGroupJob).where(TargetGroupJob.id == job_id))
        if not job:
            raise ValueError(f"Target group job {job_id} not found")
        return TargetGroupJobResponse(
            job_id=job.id,
            group_name=job.group_name,
            status=job.status.value,
            parse_status=job.parse_status.value if job.parse_status else None,
            match_status=job.match_status.value if job.match_status else None,
            original_filename=job.original_filename,
            source_file_type=job.source_file_type,
            total_rows=job.total_rows or 0,
            valid_rows=job.valid_rows or 0,
            invalid_rows=job.invalid_rows or 0,
            review_rows=job.review_rows or 0,
        )

    @classmethod
    def upload_excel(cls, db: Session, group_name: str, upload: UploadFile, actor: str = "system") -> TargetGroupUploadResponse:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(upload.filename or "target-group.xlsx").suffix or ".xlsx"
        stored_path = settings.upload_dir / f"{uuid4()}{suffix}"

        with stored_path.open("wb") as handle:
            handle.write(upload.file.read())

        fingerprint = FileHashService.fingerprint(stored_path)
        parsed_rows = ExcelImporter.read_target_group_excel(stored_path)
        preview_rows = [row.values for row in parsed_rows[:10]]
        parser_profile = parsed_rows[0].values.get("target_group_profile") if parsed_rows else "generic_excel"

        job = TargetGroupJob(
            group_name=group_name,
            original_filename=upload.filename or stored_path.name,
            stored_path=str(stored_path.resolve()),
            file_hash_sha256=fingerprint.sha256,
            source_file_type="excel",
            uploaded_by=actor,
            parse_status=ParseStatus.processing,
            match_status=ParseStatus.pending,
            status=TargetGroupStatus.uploaded,
            total_rows=len(parsed_rows),
            metadata_json={
                "future_pdf_support": "TODO",
                "target_group_profile": parser_profile,
                "source_suffix": suffix.lower(),
            },
        )
        db.add(job)
        db.flush()

        issues: list[ValidationIssue] = []
        valid_rows = 0
        invalid_rows = 0

        for parsed in parsed_rows:
            normalized, row_issues = ValidationService.validate_target_group_row(parsed.row_number, parsed.values)
            issues.extend(row_issues)
            is_valid = not row_issues
            valid_rows += int(is_valid)
            invalid_rows += int(not is_valid)
            db.add(
                TargetGroupRow(
                    job_id=job.id,
                    row_number=parsed.row_number,
                    raw_payload=parsed.values,
                    pid=normalized["pid"],
                    citizen_id=normalized["citizen_id"],
                    hn=normalized["hn"],
                    full_name=normalized["full_name"],
                    birth_date=normalized["birth_date"],
                    parse_status=ParseStatus.success if is_valid else ParseStatus.failed,
                    is_valid=is_valid,
                    validation_errors=[issue.model_dump() for issue in row_issues],
                    error_message="; ".join(issue.message for issue in row_issues) or None,
                )
            )

        job.valid_rows = valid_rows
        job.invalid_rows = invalid_rows
        job.review_rows = 0
        job.parse_status = ParseStatus.success if valid_rows or not invalid_rows else ParseStatus.failed
        job.notes = "TODO: Add PDF parsing pipeline for target group imports."

        AuditService.log(
            db,
            AuditLogCreate(
                actor=actor,
                action="target_group_uploaded",
                entity_type="target_group_job",
                entity_id=str(job.id),
                details_json={"group_name": group_name, "filename": upload.filename, "hash": fingerprint.sha256},
                new_value_json={
                    "status": job.status.value,
                    "parse_status": job.parse_status.value,
                    "valid_rows": valid_rows,
                    "invalid_rows": invalid_rows,
                },
                message="Target group uploaded for preview",
            ),
        )
        db.commit()

        return TargetGroupUploadResponse(
            job_id=job.id,
            group_name=job.group_name,
            status=job.status.value,
            total_rows=job.total_rows or 0,
            valid_rows=job.valid_rows or 0,
            invalid_rows=job.invalid_rows or 0,
            preview_rows=preview_rows,
            validation_issues=issues,
            uploaded_at=job.created_at,
        )

    @staticmethod
    def confirm_upload(db: Session, job_id: int, actor: str = "system") -> ConfirmTargetGroupResponse:
        job = db.scalar(select(TargetGroupJob).where(TargetGroupJob.id == job_id))
        if not job:
            raise ValueError(f"Target group job {job_id} not found")
        previous_status = {
            "status": job.status.value,
            "parse_status": job.parse_status.value if job.parse_status else None,
            "match_status": job.match_status.value if job.match_status else None,
        }
        job.status = TargetGroupStatus.confirmed
        job.confirmed_at = date.today()

        AuditService.log(
            db,
            AuditLogCreate(
                actor=actor,
                action="target_group_confirmed",
                entity_type="target_group_job",
                entity_id=str(job.id),
                details_json={"valid_rows": job.valid_rows, "invalid_rows": job.invalid_rows},
                old_value_json=previous_status,
                new_value_json={
                    "status": job.status.value,
                    "parse_status": job.parse_status.value if job.parse_status else None,
                    "match_status": job.match_status.value if job.match_status else None,
                },
                message="Target group confirmed for matching",
            ),
        )
        db.commit()
        return ConfirmTargetGroupResponse(
            job_id=job.id,
            status=job.status.value,
            valid_rows=job.valid_rows or 0,
            invalid_rows=job.invalid_rows or 0,
        )
