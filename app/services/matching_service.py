from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matchers.patient_matcher import PatientMatcher
from app.models.diagnosis_history import DiagnosisHistory
from app.models.disease_mapping import DiseaseMapping
from app.models.target_group import MatchStatus, ParseStatus, ResultStatus, TargetGroupJob, TargetGroupResult, TargetGroupRow, TargetGroupStatus
from app.schemas.common import AuditLogCreate
from app.schemas.matching import DiseaseMappingOptionResponse, GroupedDiseaseResponse, MatchRunResponse, SearchResultResponse, TargetGroupResultResponse
from app.services.audit_service import AuditService


class MatchingService:
    QUERY_KEY_EXPANSIONS = {
        "hpv_screen": ["cervical_screen"],
        "pap_smear_screen": ["cervical_screen"],
        "via_screen": ["cervical_screen"],
        "cervical_cancer_screen": ["cervical_screen"],
    }

    @classmethod
    def _expand_query_keys(cls, disease_keys: list[str]) -> list[str]:
        expanded: list[str] = []
        for key in disease_keys:
            for resolved_key in cls.QUERY_KEY_EXPANSIONS.get(key, [key]):
                if resolved_key not in expanded:
                    expanded.append(resolved_key)
        return expanded

    @classmethod
    def run_matching(cls, db: Session, job_id: int, actor: str = "system") -> MatchRunResponse:
        job = db.scalar(select(TargetGroupJob).where(TargetGroupJob.id == job_id))
        if not job:
            raise ValueError(f"Target group job {job_id} not found")
        previous_status = {
            "status": job.status.value,
            "match_status": job.match_status.value if job.match_status else None,
            "review_rows": job.review_rows,
        }
        job.match_status = ParseStatus.processing

        rows = db.scalars(
            select(TargetGroupRow).where(
                TargetGroupRow.job_id == job_id,
                TargetGroupRow.is_valid.is_(True),
            )
        ).all()

        db.query(TargetGroupResult).filter(TargetGroupResult.job_id == job_id).delete()

        matched_rows = 0
        review_rows = 0
        unmatched_rows = 0

        for row in rows:
            patient, method, status, flags = PatientMatcher.match_row(db, row)
            result = TargetGroupResult(
                job_id=job_id,
                target_group_row_id=row.id,
                patient_id=patient.id if patient else None,
                match_method=method,
                match_status=status,
                confidence_score="high" if status == MatchStatus.matched else None,
                flags_json=flags,
            )
            db.add(result)
            row.match_status = status
            row.matched_patient_id = patient.id if patient else None
            row.confidence_flag = "high" if status == MatchStatus.matched else "low" if status == MatchStatus.unmatched else "medium"
            row.error_message = "; ".join(flag.get("message", "") for flag in flags if flag.get("message")) or None
            if status == MatchStatus.matched:
                matched_rows += 1
            elif status == MatchStatus.needs_review:
                review_rows += 1
            else:
                unmatched_rows += 1

        job.status = TargetGroupStatus.matched
        job.matched_at = date.today()
        job.review_rows = review_rows
        job.match_status = ParseStatus.success

        AuditService.log(
            db,
            AuditLogCreate(
                actor=actor,
                action="target_group_matched",
                entity_type="target_group_job",
                entity_id=str(job.id),
                details_json={"matched_rows": matched_rows, "review_rows": review_rows, "unmatched_rows": unmatched_rows},
                old_value_json=previous_status,
                new_value_json={
                    "status": job.status.value,
                    "match_status": job.match_status.value if job.match_status else None,
                    "review_rows": review_rows,
                },
                message="Patient matching completed",
            ),
        )
        db.commit()

        return MatchRunResponse(
            job_id=job_id,
            status=job.status.value,
            matched_rows=matched_rows,
            review_rows=review_rows,
            unmatched_rows=unmatched_rows,
        )

    @classmethod
    def generate_disease_results(cls, db: Session, job_id: int, disease_keys: list[str]) -> SearchResultResponse:
        normalized_keys = [key.strip() for key in disease_keys if key and key.strip()]
        if not normalized_keys:
            raise ValueError("At least one disease key is required")
        resolved_keys = cls._expand_query_keys(normalized_keys)

        mapping_lookup = {
            item.normalized_disease_key: item.disease_group_label
            for item in db.scalars(select(DiseaseMapping).where(DiseaseMapping.is_active.is_(True))).all()
        }
        disease_codes_lookup = {
            item.normalized_disease_key: item.diagnosis_code
            for item in db.scalars(select(DiseaseMapping).where(DiseaseMapping.is_active.is_(True))).all()
        }
        results = db.scalars(select(TargetGroupResult).where(TargetGroupResult.job_id == job_id)).all()
        response_rows: list[TargetGroupResultResponse] = []

        for result in results:
            row = db.get(TargetGroupRow, result.target_group_row_id)
            selected_disease_key_value = ",".join(normalized_keys)
            if row and row.is_valid and result.patient_id is None and result.match_status != MatchStatus.unmatched:
                patient, method, status, flags = PatientMatcher.match_row(db, row)
                result.patient_id = patient.id if patient else None
                result.match_method = method
                result.match_status = status
                result.flags_json = flags
                row.match_status = status
                row.matched_patient_id = patient.id if patient else None
                row.confidence_flag = "high" if status == MatchStatus.matched else "low" if status == MatchStatus.unmatched else "medium"
                row.error_message = "; ".join(flag.get("message", "") for flag in flags if flag.get("message")) or None
            if result.patient_id:
                metrics = cls._compute_patient_metrics(db, result.patient_id, resolved_keys, mapping_lookup)
            else:
                metrics = cls._empty_metrics()
            result.selected_disease_key = selected_disease_key_value
            result.disease_key = ",".join(resolved_keys)
            result.disease_code = ",".join(sorted({disease_codes_lookup[key] for key in resolved_keys if disease_codes_lookup.get(key)})) or None
            result.disease_name = ", ".join(metrics["matched_disease_labels"] or [mapping_lookup.get(key) for key in resolved_keys if mapping_lookup.get(key)])
            result.has_disease_history = metrics["has_disease_history"]
            result.latest_visit_date = metrics["latest_visit_date"]
            result.visit_count = metrics["visit_count"]
            result.days_since_latest_visit = metrics["days_since_latest_visit"]
            result.years_since_latest_visit = metrics["years_since_latest_visit"]
            result.matched_disease_keys_json = metrics["matched_disease_keys"]
            result.matched_disease_labels_json = metrics["matched_disease_labels"]
            result.matched_service_items_json = metrics["matched_service_items"]
            result.query_filters_json = {"disease_keys": normalized_keys, "resolved_disease_keys": resolved_keys}
            result.result_status = cls._resolve_result_status(metrics["has_disease_history"])

            response_rows.append(
                TargetGroupResultResponse(
                    id=result.id,
                    row_number=row.row_number if row else 0,
                    patient_id=result.patient_id,
                    full_name=row.full_name if row else None,
                    pid=row.pid if row else None,
                    hn=row.hn if row else None,
                    match_method=result.match_method.value,
                    match_status=result.match_status.value,
                    selected_disease_key=selected_disease_key_value,
                    selected_disease_keys=normalized_keys,
                    result_status=result.result_status.value,
                    has_disease_history=metrics["has_disease_history"],
                    latest_visit_date=metrics["latest_visit_date"],
                    visit_count=metrics["visit_count"],
                    days_since_latest_visit=metrics["days_since_latest_visit"],
                    years_since_latest_visit=metrics["years_since_latest_visit"],
                    matched_disease_keys=metrics["matched_disease_keys"],
                    matched_disease_labels=metrics["matched_disease_labels"],
                    matched_service_items=metrics["matched_service_items"],
                    flags=result.flags_json,
                )
            )

        AuditService.log(
            db,
            AuditLogCreate(
                actor="system",
                action="target_group_results_generated",
                entity_type="target_group_job",
                entity_id=str(job_id),
                details_json={"disease_keys": normalized_keys, "resolved_disease_keys": resolved_keys, "row_count": len(response_rows)},
                new_value_json={"filters": {"disease_keys": normalized_keys, "resolved_disease_keys": resolved_keys}, "row_count": len(response_rows)},
                message="Disease-specific target group results generated",
            ),
        )
        db.commit()

        return SearchResultResponse(
            group_job_id=job_id,
            filters={"disease_keys": normalized_keys, "resolved_disease_keys": resolved_keys},
            results=response_rows,
        )

    @staticmethod
    def _empty_metrics() -> dict:
        return {
            "has_disease_history": None,
            "latest_visit_date": None,
            "visit_count": None,
            "days_since_latest_visit": None,
            "years_since_latest_visit": None,
            "matched_disease_keys": [],
            "matched_disease_labels": [],
            "matched_service_items": [],
        }

    @classmethod
    def _compute_patient_metrics(
        cls,
        db: Session,
        patient_id: int,
        disease_keys: list[str],
        mapping_lookup: dict[str, str | None],
    ) -> dict:
        entries = db.scalars(
            select(DiagnosisHistory).where(
                DiagnosisHistory.patient_id == patient_id,
                DiagnosisHistory.normalized_disease_key.in_(disease_keys),
            )
        ).all()
        if not entries:
            return {
                "has_disease_history": False,
                "latest_visit_date": None,
                "visit_count": 0,
                "days_since_latest_visit": None,
                "years_since_latest_visit": None,
                "matched_disease_keys": [],
                "matched_disease_labels": [],
                "matched_service_items": [],
            }

        visit_dates = [entry.visit_date for entry in entries if entry.visit_date]
        matched_disease_keys = sorted({entry.normalized_disease_key for entry in entries if entry.normalized_disease_key})
        matched_disease_labels = [
            mapping_lookup[key]
            for key in matched_disease_keys
            if key in mapping_lookup and mapping_lookup[key]
        ]
        matched_service_items = sorted({entry.disease_name_raw for entry in entries if entry.disease_name_raw})
        if not visit_dates:
            return {
                "has_disease_history": None,
                "latest_visit_date": None,
                "visit_count": len(entries),
                "days_since_latest_visit": None,
                "years_since_latest_visit": None,
                "matched_disease_keys": matched_disease_keys,
                "matched_disease_labels": matched_disease_labels,
                "matched_service_items": matched_service_items,
            }

        latest_visit = max(visit_dates)
        delta_days = (date.today() - latest_visit).days
        return {
            "has_disease_history": True,
            "latest_visit_date": latest_visit,
            "visit_count": len(entries),
            "days_since_latest_visit": delta_days,
            "years_since_latest_visit": round(delta_days / 365.25, 2),
            "matched_disease_keys": matched_disease_keys,
            "matched_disease_labels": matched_disease_labels,
            "matched_service_items": matched_service_items,
        }

    @staticmethod
    def _resolve_result_status(has_disease_history: bool | None) -> ResultStatus:
        if has_disease_history is True:
            return ResultStatus.history_found
        if has_disease_history is False:
            return ResultStatus.history_not_found
        return ResultStatus.history_unknown

    @classmethod
    def grouped_disease_summary(cls, db: Session, job_id: int) -> list[GroupedDiseaseResponse]:
        mapping_rows = db.scalars(
            select(DiseaseMapping)
            .where(DiseaseMapping.is_active.is_(True))
            .order_by(DiseaseMapping.normalized_disease_key.asc(), DiseaseMapping.disease_group_label.asc())
        ).all()
        results = db.scalars(select(TargetGroupResult).where(TargetGroupResult.job_id == job_id)).all()
        mapping_lookup = {item.normalized_disease_key: item.disease_group_label for item in mapping_rows}
        metrics_cache: dict[tuple[int, str], dict] = {}
        summaries: list[GroupedDiseaseResponse] = []
        distinct_mappings: dict[str, DiseaseMapping] = {}
        for item in mapping_rows:
            distinct_mappings.setdefault(item.normalized_disease_key, item)

        for mapping in distinct_mappings.values():
            resolved_keys = cls._expand_query_keys([mapping.normalized_disease_key])
            positive_rows = 0
            unknown_rows = 0
            for row in results:
                if not row.patient_id:
                    continue
                cache_key = (row.patient_id, ",".join(resolved_keys))
                if cache_key not in metrics_cache:
                    metrics_cache[cache_key] = cls._compute_patient_metrics(
                        db,
                        row.patient_id,
                        resolved_keys,
                        mapping_lookup,
                    )
                metric = metrics_cache[cache_key]
                if metric["has_disease_history"] is True:
                    positive_rows += 1
                elif metric["has_disease_history"] is None:
                    unknown_rows += 1

            summaries.append(
                GroupedDiseaseResponse(
                    disease_key=mapping.normalized_disease_key,
                    disease_group_label=mapping.disease_group_label,
                    total_rows=len(results),
                    matched_rows=sum(1 for row in results if row.match_status == MatchStatus.matched),
                    needs_review_rows=sum(1 for row in results if row.match_status == MatchStatus.needs_review),
                    disease_positive_rows=positive_rows,
                    disease_unknown_rows=unknown_rows,
                )
            )
        return summaries

    @staticmethod
    def disease_options(db: Session) -> list[DiseaseMappingOptionResponse]:
        mapping_rows = db.scalars(
            select(DiseaseMapping)
            .where(DiseaseMapping.is_active.is_(True))
            .order_by(DiseaseMapping.disease_group_label.asc(), DiseaseMapping.normalized_disease_key.asc())
        ).all()
        distinct_mappings: dict[str, DiseaseMapping] = {}
        for item in mapping_rows:
            distinct_mappings.setdefault(item.normalized_disease_key, item)
        return [
            DiseaseMappingOptionResponse(
                normalized_disease_key=item.normalized_disease_key,
                disease_group_label=item.disease_group_label,
                group_type=item.group_type,
                diagnosis_code=item.diagnosis_code,
                disease_name_raw=item.disease_name_raw,
            )
            for item in distinct_mappings.values()
        ]
