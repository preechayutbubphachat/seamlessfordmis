import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.target_group import TargetGroupResult, TargetGroupRow
from app.schemas.common import AuditLogCreate
from app.schemas.matching import ExportResponse
from app.services.audit_service import AuditService


class ExportService:
    @classmethod
    def export_group_results(cls, db: Session, job_id: int, actor: str = "system") -> ExportResponse:
        settings.export_dir.mkdir(parents=True, exist_ok=True)
        filename = f"target_group_results_{job_id}.xlsx"
        export_path = settings.export_dir / filename

        results = db.scalars(select(TargetGroupResult).where(TargetGroupResult.job_id == job_id)).all()
        rows: list[dict] = []
        for result in results:
            source_row = db.get(TargetGroupRow, result.target_group_row_id)
            rows.append(
                {
                    "row_number": source_row.row_number if source_row else None,
                    "full_name": source_row.full_name if source_row else None,
                    "pid": source_row.pid if source_row else None,
                    "hn": source_row.hn if source_row else None,
                    "match_method": result.match_method.value,
                    "match_status": result.match_status.value,
                    "result_status": result.result_status.value if result.result_status else None,
                    "selected_disease_key": result.selected_disease_key,
                    "disease_key": result.disease_key,
                    "disease_code": result.disease_code,
                    "disease_name": result.disease_name,
                    "has_disease_history": result.has_disease_history,
                    "latest_visit_date": result.latest_visit_date,
                    "visit_count": result.visit_count,
                    "days_since_latest_visit": result.days_since_latest_visit,
                    "years_since_latest_visit": result.years_since_latest_visit,
                    "matched_disease_keys": ", ".join(result.matched_disease_keys_json),
                    "matched_disease_labels": ", ".join(result.matched_disease_labels_json),
                    "matched_service_items": ", ".join(result.matched_service_items_json),
                    "flags_json": result.flags_json,
                }
            )

        pd.DataFrame(rows).to_excel(export_path, index=False)

        AuditService.log(
            db,
            AuditLogCreate(
                actor=actor,
                action="target_group_results_exported",
                entity_type="target_group_job",
                entity_id=str(job_id),
                details_json={"path": str(export_path.resolve()), "row_count": len(rows)},
                new_value_json={"export_path": str(export_path.resolve()), "row_count": len(rows)},
                message="Target group results exported",
            ),
        )
        db.commit()

        return ExportResponse(
            job_id=job_id,
            filename=filename,
            export_path=str(export_path.resolve()),
            row_count=len(rows),
        )
