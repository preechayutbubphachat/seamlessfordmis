from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matchers.patient_matcher import PatientMatcher
from app.models.target_group_job import TargetGroupJob
from app.models.target_group_row import TargetGroupRow
from app.schemas.target_group import RunMatchResponse
from app.services.audit_log_service import AuditLogService


class PatientMatchingService:
    @staticmethod
    def run(db: Session, group_id: UUID, actor: str = "system") -> RunMatchResponse:
        job = db.get(TargetGroupJob, group_id)
        if job is None:
            raise ValueError("ไม่พบกลุ่มเป้าหมายที่ระบุ")
        if job.total_rows == 0:
            raise ValueError("ยังไม่พบข้อมูลกลุ่มเป้าหมายสำหรับการจับคู่")

        job.match_status = "processing"
        db.add(job)
        AuditLogService.create_event(
            db,
            actor=actor,
            action="run_patient_match",
            entity_type="target_group_jobs",
            entity_id=str(group_id),
            status="started",
            context={"total_rows": job.total_rows},
        )
        db.commit()

        try:
            rows = db.scalars(select(TargetGroupRow).where(TargetGroupRow.group_job_id == group_id)).all()
            counts = {"matched": 0, "not_found": 0, "ambiguous": 0, "needs_review": 0}

            for row in rows:
                if row.validation_status == "invalid":
                    row.match_status = "needs_review"
                    row.match_method = "needs_review"
                    row.matched_patient_id = None
                    row.matched_identifier_basis = None
                    row.matched_name_basis = None
                    row.confidence_flag = "low"
                    db.add(row)
                    counts["needs_review"] += 1
                    continue

                decision = PatientMatcher.match(db, row)
                row.match_status = decision.match_status
                row.match_method = decision.match_method
                row.matched_patient_id = decision.patient.id if decision.patient else None
                row.matched_identifier_basis = decision.matched_identifier_basis
                row.matched_name_basis = decision.matched_name_basis
                row.confidence_flag = decision.match_confidence
                db.add(row)
                counts[decision.match_status] += 1

            job.match_status = "success"
            db.add(job)
            AuditLogService.create_event(
                db,
                actor=actor,
                action="run_patient_match",
                entity_type="target_group_jobs",
                entity_id=str(group_id),
                status="success",
                context=counts,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            persisted_job = db.get(TargetGroupJob, group_id)
            if persisted_job is not None:
                persisted_job.match_status = "failed"
                db.add(persisted_job)
                AuditLogService.create_event(
                    db,
                    actor=actor,
                    action="run_patient_match",
                    entity_type="target_group_jobs",
                    entity_id=str(group_id),
                    status="failed",
                    context={"total_rows": persisted_job.total_rows},
                    error_summary=str(exc),
                )
                db.commit()
            raise

        return RunMatchResponse(
            group_id=group_id,
            match_status=job.match_status,
            matched_rows=counts["matched"],
            not_found_rows=counts["not_found"],
            ambiguous_rows=counts["ambiguous"],
            needs_review_rows=counts["needs_review"],
        )
