import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from math import ceil
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, text
from app.db.compat import make_upsert_stmt as _make_upsert_stmt
from sqlalchemy.orm import Session

from app.models.disease_mapping import DiseaseMapping
from app.services.field_mapping_service import _THAI_SERVICE_SLUG_TO_CANONICAL
from app.models.disease_screening_record import DiseaseScreeningRecord
from app.models.target_group_history_row import TargetGroupHistoryRow
from app.models.target_group_job import TargetGroupJob
from app.models.target_group_result import TargetGroupResult
from app.models.target_group_result_summary import TargetGroupResultSummary
from app.models.target_group_row import TargetGroupRow
from app.schemas.result import (
    GenerateResultsResponse,
    GroupResultsResponse,
    GroupResultRowResponse,
    ResultSummaryResponse,
    ServiceBreakdownResponse,
)
from app.services.audit_log_service import AuditLogService
from app.utils.dates import compute_visit_metrics
from app.utils.text_normalization import normalize_service_key, normalize_text, parse_service_date


DEFAULT_OVERDUE_YEARS = 1
# Bump whenever result-row classification / normalization logic changes in a way
# that would make previously-generated (cached) results stale even though the
# source files are unchanged. A cached summary stamped with an older version is
# flagged so the UI can prompt the user to regenerate. Do NOT auto-regenerate.
#   v1: initial
#   v2: roster-derived target-group history counted in classification (D4.7.6)
RESULT_NORMALIZATION_VERSION = 2
OUTSIDE_SCOPE_RESULT_STATUSES = {"non_thai_nationality", "outside_target_scope"}
IDENTITY_EXCLUDED_RESULT_STATUSES = {
    "invalid_identifier",
    "missing_identifier",
    "insufficient_identity_data",
    "review_required_identity",
    *OUTSIDE_SCOPE_RESULT_STATUSES,
}
NON_HISTORY_SCREENING_STATUSES = {
    "invalid_identifier",
    "missing_identifier",
    "needs_review",
    "review_required_identity",
    "non_thai_nationality",
    "outside_target_scope",
    "insufficient_identity_data",
}
THAI_NATIONALITY_VALUES = {"ไทย", "thai", "thai nationality", "thai national"}


@dataclass(frozen=True)
class TargetGroupHistoryEvidence:
    source_type: str
    source_file_name: str | None
    source_sheet_name: str | None
    source_row_no: int | None
    normalized_cid: str | None
    normalized_full_name: str | None
    normalized_birth_date: date | None
    normalized_address: str | None
    raw_nationality: str | None
    raw_service_type: str | None
    normalized_service_key: str | None
    normalized_visit_date: date | None
    raw_result: str | None
    raw_hospital: str | None
    raw_doctor: str | None
    raw_note: str | None
    warning_message: str | None


@dataclass(frozen=True)
class PersonResultContext:
    key: str
    rows: list[TargetGroupRow]
    primary_row: TargetGroupRow


class ResultGenerationService:
    @staticmethod
    def generate(db: Session, group_id: UUID, disease_keys: list[str], actor: str = "system") -> GenerateResultsResponse:
        selected_service_keys = ResultGenerationService._normalize_selected_service_keys(disease_keys)
        if not selected_service_keys:
            raise ValueError("ต้องเลือกรายการโรคหรือบริการอย่างน้อย 1 รายการก่อนสร้างผลลัพธ์")

        selected_service_hash = ResultGenerationService._selection_hash(selected_service_keys)

        job = db.get(TargetGroupJob, group_id)
        current_source_set_hash: str | None = job.source_set_hash if job else None

        existing_rows = db.scalars(
            select(TargetGroupResult)
            .where(TargetGroupResult.group_job_id == group_id)
            .order_by(TargetGroupResult.generated_at.desc())
        ).all()
        if ResultGenerationService._can_reuse_existing_results(existing_rows, selected_service_hash):
            summary = ResultGenerationService._build_summary(
                existing_rows,
                selected_service_keys,
                existing_rows[0].generated_at,
                overdue_years=DEFAULT_OVERDUE_YEARS,
                source_set_hash=current_source_set_hash,
            )
            breakdown = ResultGenerationService._build_breakdown_from_screening(db, existing_rows, selected_service_keys)
            AuditLogService.create_event(
                db,
                actor=actor,
                action="generate_group_results",
                entity_type="target_group_jobs",
                entity_id=str(group_id),
                status="reused",
                context={
                    "selected_service_keys": selected_service_keys,
                    "selected_service_hash": selected_service_hash,
                    "generated_rows": len(existing_rows),
                },
            )
            ResultGenerationService._upsert_summary_cache(db, summary, DEFAULT_OVERDUE_YEARS, source_set_hash=current_source_set_hash)
            db.commit()
            return GenerateResultsResponse(
                group_id=group_id,
                generated_rows=len(existing_rows),
                disease_keys=selected_service_keys,
                summary=summary,
                breakdown=breakdown,
            )

        AuditLogService.create_event(
            db,
            actor=actor,
            action="generate_group_results",
            entity_type="target_group_jobs",
            entity_id=str(group_id),
            status="started",
            context={
                "selected_service_keys": selected_service_keys,
                "selected_service_hash": selected_service_hash,
            },
        )
        db.commit()

        try:
            rows = db.scalars(
                select(TargetGroupRow)
                .where(TargetGroupRow.group_job_id == group_id)
                .order_by(TargetGroupRow.row_no.asc(), TargetGroupRow.created_at.asc())
            ).all()
            if not rows:
                raise ValueError("ยังไม่พบข้อมูลกลุ่มเป้าหมายสำหรับสร้างผลลัพธ์")

            person_contexts = ResultGenerationService._build_person_contexts(rows)
            mapping_rows = db.scalars(
                select(DiseaseMapping).where(DiseaseMapping.normalized_key.in_(selected_service_keys))
            ).all()
            labels_by_key = {row.normalized_key: row.normalized_label for row in mapping_rows}
            legacy_disease_key = selected_service_keys[0] if len(selected_service_keys) == 1 else None
            legacy_disease_name = labels_by_key.get(legacy_disease_key) if legacy_disease_key else None
            _, record_key_to_selected_keys = ResultGenerationService._expand_selected_service_keys(
                mapping_rows,
                selected_service_keys,
            )
            eligible_record_keys = sorted(record_key_to_selected_keys)

            screening_records = db.scalars(
                select(DiseaseScreeningRecord).where(
                    DiseaseScreeningRecord.normalized_service_key.in_(eligible_record_keys)
                )
            ).all()
            screening_by_identifier: dict[str, list[DiseaseScreeningRecord]] = defaultdict(list)
            for record in screening_records:
                screening_by_identifier[record.normalized_person_identifier].append(record)

            history_rows = ResultGenerationService._load_selected_target_group_history_rows(
                db,
                group_id,
                eligible_record_keys,
            )
            history_by_identifier, history_by_name_without_identifier = ResultGenerationService._index_target_group_history_rows(
                history_rows
            )

            db.execute(delete(TargetGroupResult).where(TargetGroupResult.group_job_id == group_id))

            breakdown_people: dict[str, set[str]] = {key: set() for key in selected_service_keys}
            breakdown_counts: dict[str, int] = {key: 0 for key in selected_service_keys}
            generated_at = datetime.now()

            for context in person_contexts:
                primary_row = context.primary_row
                identifier_basis = ResultGenerationService._result_identifier_basis_for_rows(context.rows)
                eligible_records = ResultGenerationService._collect_screening_records_for_rows(
                    context.rows,
                    screening_by_identifier,
                )
                eligible_history_rows = ResultGenerationService._collect_target_group_history_matches(
                    context.rows,
                    history_by_identifier,
                    history_by_name_without_identifier,
                )
                row_payload = ResultGenerationService._build_row_result_payload_for_rows(
                    context.rows,
                    eligible_records,
                    eligible_history_rows,
                    record_key_to_selected_keys,
                )
                person_link_status_val, duplicate_reason_val, review_required_val = (
                    ResultGenerationService._person_link_details(context.rows)
                )

                for record in eligible_records:
                    for service_key in record_key_to_selected_keys.get(record.normalized_service_key, {record.normalized_service_key}):
                        breakdown_counts[service_key] += 1
                        if identifier_basis:
                            breakdown_people[service_key].add(identifier_basis)
                for history_event in eligible_history_rows:
                    for service_key in record_key_to_selected_keys.get(
                        history_event.normalized_service_key or "",
                        {history_event.normalized_service_key},
                    ):
                        if not service_key:
                            continue
                        breakdown_counts[service_key] += 1
                        history_basis = history_event.normalized_cid or history_event.normalized_full_name or identifier_basis
                        if history_basis:
                            breakdown_people[service_key].add(history_basis)

                db.add(
                    TargetGroupResult(
                        group_job_id=group_id,
                        target_row_id=primary_row.id,
                        patient_id=primary_row.matched_patient_id,
                        disease_key=legacy_disease_key,
                        disease_name=legacy_disease_name,
                        visit_count=row_payload["matching_record_count"],
                        normalized_cid=primary_row.normalized_cid,
                        full_name=primary_row.normalized_full_name or primary_row.raw_full_name,
                        age=primary_row.normalized_age,
                        sex=primary_row.normalized_sex,
                        has_selected_service=row_payload["has_selected_service"],
                        matching_record_count=row_payload["matching_record_count"],
                        matched_service_keys=row_payload["matched_service_keys"],
                        selected_service_keys=selected_service_keys,
                        selected_service_hash=selected_service_hash,
                        last_visit_date=row_payload["last_visit_date"],
                        days_since_last_visit=row_payload["days_since_last_visit"],
                        years_since_last_visit=Decimal(str(row_payload["years_since_last_visit"]))
                        if row_payload["years_since_last_visit"] is not None
                        else None,
                        result_status=row_payload["result_status"],
                        warning_message=row_payload["warning_message"],
                        generated_at=generated_at,
                        canonical_person_key=context.key,
                        person_link_status=person_link_status_val,
                        review_required=review_required_val,
                        duplicate_reason=duplicate_reason_val,
                    )
                )

            db.flush()

            persisted_rows = db.scalars(
                select(TargetGroupResult)
                .where(TargetGroupResult.group_job_id == group_id)
                .order_by(TargetGroupResult.generated_at.desc(), TargetGroupResult.full_name.asc().nullslast())
            ).all()
            summary = ResultGenerationService._build_summary(
                persisted_rows,
                selected_service_keys,
                generated_at,
                overdue_years=DEFAULT_OVERDUE_YEARS,
                source_set_hash=current_source_set_hash,
            )
            breakdown = [
                ServiceBreakdownResponse(
                    selected_service_key=service_key,
                    distinct_people_count=len(breakdown_people[service_key]),
                    matching_record_count=breakdown_counts[service_key],
                )
                for service_key in selected_service_keys
            ]

            AuditLogService.create_event(
                db,
                actor=actor,
                action="generate_group_results",
                entity_type="target_group_jobs",
                entity_id=str(group_id),
                status="success",
                context={
                    "selected_service_keys": selected_service_keys,
                    "selected_service_hash": selected_service_hash,
                    "generated_rows": len(persisted_rows),
                    "summary": summary.model_dump(mode="json"),
                },
            )
            ResultGenerationService._upsert_summary_cache(db, summary, DEFAULT_OVERDUE_YEARS, source_set_hash=current_source_set_hash)
            db.commit()
            return GenerateResultsResponse(
                group_id=group_id,
                generated_rows=len(persisted_rows),
                disease_keys=selected_service_keys,
                summary=summary,
                breakdown=breakdown,
            )
        except Exception as exc:
            db.rollback()
            AuditLogService.create_event(
                db,
                actor=actor,
                action="generate_group_results",
                entity_type="target_group_jobs",
                entity_id=str(group_id),
                status="failed",
                context={
                    "selected_service_keys": selected_service_keys,
                    "selected_service_hash": selected_service_hash,
                },
                error_summary=str(exc),
            )
            db.commit()
            raise

    @staticmethod
    def get_results(
        db: Session,
        group_id: UUID,
        overdue_years: int = DEFAULT_OVERDUE_YEARS,
        page: int = 1,
        page_size: int = 100,
        view: str | None = None,
        query: str | None = None,
        overdue_enabled: bool = False,
        include_all: bool = False,
        sort_col: str | None = None,
        sort_dir: str | None = None,
    ) -> GroupResultsResponse:
        # Phase E: use summary cache (O(1)) or aggregate SQL fallback via get_result_summary.
        # Returns total_target_people=0 when no results have been generated yet.
        summary = ResultGenerationService.get_result_summary(db, group_id, overdue_years)
        if summary.total_target_people == 0:
            empty_summary = ResultSummaryResponse(
                group_job_id=group_id,
                total_target_people=0,
                valid_identifier_people=0,
                invalid_identifier_people=0,
                non_thai_nationality_people=0,
                insufficient_identity_people=0,
                outside_target_scope_people=0,
                review_required_identity_people=0,
                people_with_selected_history=0,
                people_without_selected_history=0,
                never_checked_people=0,
                checked_but_overdue_people=0,
                checked_and_within_threshold_people=0,
                coverage_percent=0.0,
                coverage_denominator_people=0,
                overdue_threshold_years=overdue_years,
                selected_service_count=0,
                selected_service_keys=[],
                generated_at=None,
            )
            return GroupResultsResponse(
                group_id=group_id,
                summary=empty_summary,
                breakdown=[],
                results=[],
                page=page,
                page_size=page_size,
                total_filtered_rows=0,
                total_pages=0,
            )

        selected_service_keys = summary.selected_service_keys
        # Load a lightweight representative row only for breakdown (needs group_id + service keys)
        rep_row = db.scalars(
            select(TargetGroupResult)
            .where(TargetGroupResult.group_job_id == group_id)
            .limit(1)
        ).first()
        breakdown = ResultGenerationService._build_breakdown_from_screening(db, [rep_row] if rep_row else [], selected_service_keys)
        filtered_row_ids = ResultGenerationService._query_filtered_result_ids(
            db,
            group_id=group_id,
            overdue_years=overdue_years,
            view=view,
            query=query,
            overdue_enabled=overdue_enabled,
            sort_col=sort_col,
            sort_dir=sort_dir,
        )
        total_filtered_rows = len(filtered_row_ids)
        if include_all:
            total_pages = 1 if total_filtered_rows else 0
            page = 1
            page_ids = filtered_row_ids
            response_page_size = total_filtered_rows or page_size
        else:
            total_pages = ceil(total_filtered_rows / page_size) if total_filtered_rows else 0
            page = min(page, total_pages) if total_pages else 1
            page = max(page, 1)
            start = (page - 1) * page_size
            page_ids = filtered_row_ids[start : start + page_size]
            response_page_size = page_size

        paged_rows_map = {
            row.id: row
            for row in db.scalars(
                select(TargetGroupResult).where(TargetGroupResult.id.in_(page_ids))
            ).all()
        } if page_ids else {}
        paged_rows = [paged_rows_map[row_id] for row_id in page_ids if row_id in paged_rows_map]

        # Phase E: load only the TargetGroupRow records for this page's primary rows
        # instead of all rows for the group.  Phase D stores person_link_status /
        # review_required / duplicate_reason directly on TargetGroupResult, so the
        # full multi-row context is only needed for provenance details and the rare
        # pre-Phase D fallback.  Loading O(page_size) rows instead of O(total_rows)
        # eliminates the dominant latency hotspot on large groups.
        page_target_row_ids = [r.target_row_id for r in paged_rows if r.target_row_id is not None]
        page_target_rows_by_id: dict[UUID, TargetGroupRow] = (
            {
                row.id: row
                for row in db.scalars(
                    select(TargetGroupRow).where(TargetGroupRow.id.in_(page_target_row_ids))
                ).all()
            }
            if page_target_row_ids
            else {}
        )

        history_rows = ResultGenerationService._load_selected_target_group_history_rows(
            db,
            group_id,
            sorted(ResultGenerationService._expand_selected_service_keys(
                db.scalars(select(DiseaseMapping).where(DiseaseMapping.normalized_key.in_(selected_service_keys))).all(),
                selected_service_keys,
            )[1]),
        )
        history_by_identifier, history_by_name_without_identifier = ResultGenerationService._index_target_group_history_rows(history_rows)

        return GroupResultsResponse(
            group_id=group_id,
            summary=summary,
            breakdown=breakdown,
            results=[
                ResultGenerationService._build_result_row_response(
                    result,
                    (page_rows := (
                        [page_target_rows_by_id[result.target_row_id]]
                        if result.target_row_id in page_target_rows_by_id
                        else []
                    )),
                    ResultGenerationService._collect_target_group_history_matches(
                        page_rows,
                        history_by_identifier,
                        history_by_name_without_identifier,
                    ),
                    overdue_years,
                )
                for result in paged_rows
            ],
            page=page,
            page_size=response_page_size,
            total_filtered_rows=total_filtered_rows,
            total_pages=total_pages,
        )

    @staticmethod
    def get_result_summary(db: Session, group_id: UUID, overdue_years: int = DEFAULT_OVERDUE_YEARS) -> ResultSummaryResponse:
        # Phase E: try the summary cache first (written at generate() time).
        # This is a single primary-key lookup — O(1) — avoiding all aggregation.
        cached = db.scalars(
            select(TargetGroupResultSummary)
            .where(TargetGroupResultSummary.group_job_id == group_id)
            .order_by(TargetGroupResultSummary.generated_at.desc())
            .limit(1)
        ).first()
        if cached is not None:
            valid = cached.valid_identifier_people
            return ResultSummaryResponse(
                group_job_id=group_id,
                total_target_people=cached.total_target_people,
                valid_identifier_people=valid,
                invalid_identifier_people=cached.invalid_identifier_people,
                non_thai_nationality_people=cached.non_thai_nationality_people,
                insufficient_identity_people=cached.insufficient_identity_people,
                outside_target_scope_people=cached.outside_target_scope_people,
                review_required_identity_people=cached.review_required_identity_people,
                people_with_selected_history=cached.people_with_selected_history,
                people_without_selected_history=cached.people_without_selected_history,
                never_checked_people=cached.never_checked_people,
                checked_but_overdue_people=cached.checked_but_overdue_people,
                checked_and_within_threshold_people=cached.checked_and_within_threshold_people,
                coverage_percent=float(cached.coverage_percent),
                coverage_denominator_people=valid,
                overdue_threshold_years=cached.overdue_threshold_years or overdue_years,
                selected_service_count=len(cached.selected_service_keys),
                selected_service_keys=cached.selected_service_keys,
                generated_at=cached.generated_at,
                generated_source_set_hash=cached.source_set_hash,
                normalization_version=cached.normalization_version,
                current_normalization_version=RESULT_NORMALIZATION_VERSION,
                # Cached rows generated before this column (NULL) or with an older
                # version are stale → prompt regenerate (never auto-regenerate).
                requires_regeneration=(cached.normalization_version or 0) < RESULT_NORMALIZATION_VERSION,
            )
        # Fallback: compute on-the-fly with aggregate SQL for groups generated
        # before the summary cache table existed (pre-migration 0012).
        sql_summary = ResultGenerationService._build_summary_from_sql(db, group_id, overdue_years)
        if sql_summary is not None:
            return sql_summary
        return ResultSummaryResponse(
            group_job_id=group_id,
            total_target_people=0,
            valid_identifier_people=0,
            invalid_identifier_people=0,
            non_thai_nationality_people=0,
            insufficient_identity_people=0,
            outside_target_scope_people=0,
            review_required_identity_people=0,
            people_with_selected_history=0,
            people_without_selected_history=0,
            never_checked_people=0,
            checked_but_overdue_people=0,
            checked_and_within_threshold_people=0,
            coverage_percent=0.0,
            coverage_denominator_people=0,
            overdue_threshold_years=overdue_years,
            selected_service_count=0,
            selected_service_keys=[],
            generated_at=None,
        )

    @staticmethod
    def _build_person_contexts(rows: list[TargetGroupRow]) -> list[PersonResultContext]:
        grouped: dict[str, list[TargetGroupRow]] = defaultdict(list)
        for row in rows:
            grouped[ResultGenerationService._person_group_key(row)].append(row)
        contexts: list[PersonResultContext] = []
        for key, grouped_rows in grouped.items():
            ordered_rows = sorted(grouped_rows, key=ResultGenerationService._row_sort_key)
            contexts.append(PersonResultContext(key=key, rows=ordered_rows, primary_row=ordered_rows[0]))
        return sorted(contexts, key=lambda item: ResultGenerationService._row_sort_key(item.primary_row))

    @staticmethod
    def _person_group_key(row: TargetGroupRow) -> str:
        if row.matched_identifier_basis:
            return f"identifier:{row.matched_identifier_basis}"
        if row.normalized_cid and row.cid_validation_status == "valid_identifier":
            return f"cid:{row.normalized_cid}"
        if row.normalized_full_name and row.normalized_birth_date:
            return f"name_birth:{row.normalized_full_name}:{row.normalized_birth_date.isoformat()}"
        normalized_address = ResultGenerationService._normalized_address_for_row(row)
        if row.normalized_full_name and normalized_address:
            # Row number alone is unsafe across multi-file uploads, so we use
            # provenance-backed identity hints and keep this bucket reviewable.
            return f"review_name_address:{row.normalized_full_name}:{normalized_address}"
        if row.normalized_full_name:
            return f"review_name:{row.normalized_full_name}"
        return f"row:{row.id}"

    @staticmethod
    def _normalized_address_for_row(row: TargetGroupRow) -> str | None:
        return normalize_text((row.raw_json or {}).get("address") or (row.raw_json or {}).get("ที่อยู่"))

    @staticmethod
    def _normalized_nationality_for_row(row: TargetGroupRow) -> str | None:
        return normalize_text((row.raw_json or {}).get("nationality") or (row.raw_json or {}).get("สัญชาติ"))

    @staticmethod
    def _is_non_thai_nationality(rows: list[TargetGroupRow]) -> bool:
        for row in rows:
            nationality = ResultGenerationService._normalized_nationality_for_row(row)
            if not nationality:
                continue
            if nationality.casefold() not in THAI_NATIONALITY_VALUES:
                return True
        return False

    @staticmethod
    def _has_identifier_eligible_scope(rows: list[TargetGroupRow]) -> bool:
        return any(
            row.cid_validation_status == "valid_identifier"
            or (row.normalized_full_name and row.normalized_birth_date)
            for row in rows
        )

    @staticmethod
    def _has_reviewable_identity(rows: list[TargetGroupRow]) -> bool:
        return any(
            row.normalized_full_name and ResultGenerationService._normalized_address_for_row(row)
            for row in rows
        )

    @staticmethod
    def _person_link_details(rows: list[TargetGroupRow]) -> tuple[str, str | None, bool]:
        if any(row.cid_validation_status == "valid_identifier" and row.normalized_cid for row in rows):
            return "citizen_id_exact", "รวมข้อมูลด้วยเลขบัตรประชาชน 13 หลักตรงกัน", False
        if any(row.normalized_full_name and row.normalized_birth_date for row in rows):
            return "name_birthdate_exact", "รวมข้อมูลด้วยชื่อ-สกุลและวันเกิดตรงกัน", False
        if ResultGenerationService._has_reviewable_identity(rows):
            return "name_birthdate_address_secondary", "ใช้ชื่อร่วมกับที่อยู่เป็นหลักฐานสนับสนุนและควรตรวจสอบก่อนใช้งานต่อ", True
        if any(row.normalized_full_name for row in rows):
            return "review_required", "มีเพียงชื่อหรือข้อมูลระบุตัวตนไม่พอ จึงยังไม่รวมแบบมั่นใจ", True
        return "insufficient_identity_data", "ข้อมูลระบุตัวตนไม่พอสำหรับเชื่อมโยงบุคคลอย่างปลอดภัย", True

    @staticmethod
    def _row_sort_key(row: TargetGroupRow) -> tuple:
        return (
            0 if row.cid_validation_status == "valid_identifier" else 1,
            0 if row.match_status == "matched" else 1,
            0 if row.matched_identifier_basis else 1,
            0 if row.normalized_cid else 1,
            0 if row.normalized_full_name else 1,
            row.source_row_no if row.source_row_no is not None else row.row_no,
            str(row.id),
        )

    @staticmethod
    def _load_selected_target_group_history_rows(
        db: Session,
        group_id: UUID,
        eligible_record_keys: list[str],
    ) -> list[TargetGroupHistoryRow]:
        if not eligible_record_keys:
            return []
        return db.scalars(
            select(TargetGroupHistoryRow).where(
                TargetGroupHistoryRow.group_job_id == group_id,
                TargetGroupHistoryRow.normalized_service_key.in_(eligible_record_keys),
            )
        ).all()

    @staticmethod
    def _index_target_group_history_rows(
        history_rows: list[TargetGroupHistoryRow],
    ) -> tuple[dict[str, list[TargetGroupHistoryEvidence]], dict[str, list[TargetGroupHistoryEvidence]]]:
        by_identifier: dict[str, list[TargetGroupHistoryEvidence]] = defaultdict(list)
        by_name_without_identifier: dict[str, list[TargetGroupHistoryEvidence]] = defaultdict(list)
        for row in history_rows:
            evidence = ResultGenerationService._history_evidence_from_model(row)
            if evidence.normalized_cid:
                by_identifier[evidence.normalized_cid].append(evidence)
            elif evidence.normalized_full_name:
                by_name_without_identifier[evidence.normalized_full_name].append(evidence)
        return by_identifier, by_name_without_identifier

    @staticmethod
    def _history_evidence_from_model(row: TargetGroupHistoryRow) -> TargetGroupHistoryEvidence:
        # Use pre-normalized columns directly from the model rather than
        # re-parsing raw_json, which may not have consistent key names and
        # is slower.  normalized_birth_date / normalized_address are stored
        # during staging by validate_target_group_history_row().
        raw_json = row.raw_json or {}
        return TargetGroupHistoryEvidence(
            source_type="target_group_history_sheet",
            source_file_name=row.source_file_name,
            source_sheet_name=row.source_sheet_name,
            source_row_no=row.source_row_no,
            normalized_cid=row.normalized_cid,
            normalized_full_name=row.normalized_full_name,
            normalized_birth_date=row.normalized_birth_date,
            normalized_address=row.normalized_address,
            raw_nationality=normalize_text(raw_json.get("nationality") or raw_json.get("สัญชาติ")),
            raw_service_type=row.raw_service_type,
            normalized_service_key=row.normalized_service_key,
            normalized_visit_date=row.normalized_visit_date,
            raw_result=row.raw_result,
            raw_hospital=row.raw_hospital,
            raw_doctor=row.raw_doctor,
            raw_note=row.raw_note,
            warning_message=row.warning_message,
        )

    @staticmethod
    def _embedded_history_from_target_row(row: TargetGroupRow) -> list[TargetGroupHistoryEvidence]:
        if not row.normalized_target_history_last_visit_date:
            return []
        service_keys = row.normalized_target_history_service_keys or []
        canonical_service_key = ResultGenerationService._canonical_embedded_service_key(service_keys)
        if not canonical_service_key:
            return []
        return [
            TargetGroupHistoryEvidence(
                source_type="target_group_roster_context",
                source_file_name=row.source_file_name,
                source_sheet_name=(row.raw_json or {}).get("source_sheet_name"),
                source_row_no=row.source_row_no,
                normalized_cid=row.normalized_cid,
                normalized_full_name=row.normalized_full_name,
                normalized_birth_date=row.normalized_birth_date,
                normalized_address=ResultGenerationService._normalized_address_for_row(row),
                raw_nationality=ResultGenerationService._read_target_group_raw_value(row, "nationality"),
                raw_service_type=row.raw_target_history_labels,
                normalized_service_key=canonical_service_key,
                normalized_visit_date=row.normalized_target_history_last_visit_date,
                raw_result=row.raw_target_history_labels,
                raw_hospital=None,
                raw_doctor=None,
                raw_note=row.raw_target_history_note,
                warning_message="derived_from_roster_history_context",
            )
        ]

    @staticmethod
    def _canonical_embedded_service_key(service_keys: list[str]) -> str | None:
        cleaned = [item for item in service_keys if item]
        if "cervical_screen" in cleaned:
            return "cervical_screen"
        if cleaned:
            return sorted(set(cleaned))[0]
        return None

    @staticmethod
    def _collect_screening_records_for_rows(
        rows: list[TargetGroupRow],
        screening_by_identifier: dict[str, list[DiseaseScreeningRecord]],
    ) -> list[DiseaseScreeningRecord]:
        collected: list[DiseaseScreeningRecord] = []
        for basis in ResultGenerationService._candidate_identifier_bases(rows):
            collected.extend(screening_by_identifier.get(basis, []))
        deduped: dict[tuple, DiseaseScreeningRecord] = {}
        for record in collected:
            key = (
                record.source_import_job_id,
                record.source_file_id,
                record.source_row_no,
                record.normalized_person_identifier,
                record.normalized_service_key,
                record.visit_date,
                record.transaction_id,
            )
            deduped[key] = record
        return list(deduped.values())

    @staticmethod
    def _collect_target_group_history_matches(
        rows: list[TargetGroupRow],
        history_by_identifier: dict[str, list[TargetGroupHistoryEvidence]],
        history_by_name_without_identifier: dict[str, list[TargetGroupHistoryEvidence]],
    ) -> list[TargetGroupHistoryEvidence]:
        collected: list[TargetGroupHistoryEvidence] = []
        for row in rows:
            row_had_identifier_match = False
            if row.normalized_cid:
                identifier_matches = history_by_identifier.get(row.normalized_cid, [])
                if identifier_matches:
                    collected.extend(identifier_matches)
                    row_had_identifier_match = True
            if not row_had_identifier_match and row.normalized_full_name:
                collected.extend(
                    ResultGenerationService._match_history_candidates_for_row(
                        row,
                        history_by_name_without_identifier.get(row.normalized_full_name, []),
                    )
                )
            collected.extend(ResultGenerationService._embedded_history_from_target_row(row))

        deduped: dict[tuple, TargetGroupHistoryEvidence] = {}
        for item in collected:
            key = (
                item.normalized_cid or item.normalized_full_name,
                item.normalized_service_key,
                item.normalized_visit_date,
                item.raw_result,
                item.raw_hospital,
                item.raw_doctor,
                item.raw_note,
            )
            deduped[key] = item
        return list(deduped.values())

    @staticmethod
    def _match_history_candidates_for_row(
        row: TargetGroupRow,
        candidates: list[TargetGroupHistoryEvidence],
    ) -> list[TargetGroupHistoryEvidence]:
        if not candidates:
            return []

        comparable_candidates = [
            candidate
            for candidate in candidates
            if not (
                row.normalized_birth_date
                and candidate.normalized_birth_date
                and candidate.normalized_birth_date != row.normalized_birth_date
            )
        ]

        exact_birthdate_matches = [
            candidate
            for candidate in comparable_candidates
            if row.normalized_birth_date and candidate.normalized_birth_date == row.normalized_birth_date
        ]
        if exact_birthdate_matches:
            return exact_birthdate_matches

        row_address = ResultGenerationService._normalized_address_for_row(row)
        if row_address:
            address_matches = [
                candidate
                for candidate in comparable_candidates
                if candidate.normalized_address and candidate.normalized_address == row_address
            ]
            if address_matches:
                return address_matches

        return []

    @staticmethod
    def _candidate_identifier_bases(rows: list[TargetGroupRow]) -> list[str]:
        ordered: list[str] = []
        for row in rows:
            basis = ResultGenerationService._result_identifier_basis(row)
            if basis and basis not in ordered:
                ordered.append(basis)
        return ordered

    @staticmethod
    def _resolve_context_rows(
        result: TargetGroupResult,
        contexts_by_key: dict[str, "PersonResultContext"],
        contexts_by_primary_id: dict[UUID, "PersonResultContext"],
    ) -> list[TargetGroupRow]:
        # Phase D: prefer lookup by canonical_person_key (stored, stable).
        # Fall back to target_row_id for results generated before Phase D migration.
        if result.canonical_person_key and result.canonical_person_key in contexts_by_key:
            return contexts_by_key[result.canonical_person_key].rows
        if result.target_row_id and result.target_row_id in contexts_by_primary_id:
            return contexts_by_primary_id[result.target_row_id].rows
        return []

    @staticmethod
    def _load_target_rows(db: Session, rows: list[TargetGroupResult]) -> dict[UUID, list[TargetGroupRow]]:
        group_ids = {row.group_job_id for row in rows}
        if not rows or len(group_ids) != 1:
            return {}
        group_id = next(iter(group_ids))
        group_rows = db.scalars(
            select(TargetGroupRow)
            .where(TargetGroupRow.group_job_id == group_id)
            .order_by(TargetGroupRow.row_no.asc(), TargetGroupRow.created_at.asc())
        ).all()
        contexts = ResultGenerationService._build_person_contexts(group_rows)
        return {context.primary_row.id: context.rows for context in contexts}

    @staticmethod
    def _load_target_group_history_matches_for_rows(
        db: Session,
        group_id: UUID,
        target_rows: dict[UUID, list[TargetGroupRow]],
        selected_service_keys: list[str],
    ) -> dict[UUID, list[TargetGroupHistoryEvidence]]:
        if not target_rows:
            return {}

        mapping_rows = db.scalars(
            select(DiseaseMapping).where(DiseaseMapping.normalized_key.in_(selected_service_keys))
        ).all()
        _, record_key_to_selected_keys = ResultGenerationService._expand_selected_service_keys(
            mapping_rows,
            selected_service_keys,
        )
        eligible_record_keys = sorted(record_key_to_selected_keys) or selected_service_keys
        history_rows = ResultGenerationService._load_selected_target_group_history_rows(
            db,
            group_id,
            eligible_record_keys,
        )
        history_by_identifier, history_by_name_without_identifier = ResultGenerationService._index_target_group_history_rows(history_rows)

        matches: dict[UUID, list[TargetGroupHistoryEvidence]] = {}
        for primary_row_id, grouped_rows in target_rows.items():
            matches[primary_row_id] = ResultGenerationService._collect_target_group_history_matches(
                grouped_rows,
                history_by_identifier,
                history_by_name_without_identifier,
            )
        return matches

    @staticmethod
    def _build_result_row_response(
        result: TargetGroupResult,
        target_rows: list[TargetGroupRow],
        target_group_history_rows: list[TargetGroupHistoryEvidence],
        overdue_years: int,
    ) -> GroupResultRowResponse:
        primary_row = target_rows[0] if target_rows else None
        screening_status = ResultGenerationService._screening_status_for_result(result, overdue_years)
        matched_identifier = result.normalized_cid
        if primary_row and primary_row.matched_identifier_basis:
            matched_identifier = primary_row.matched_identifier_basis

        history_found_in_screening_db = result.result_status in {"screening_db_only", "both_sources"}
        history_found_in_target_group_file = result.result_status in {"target_group_file_only", "both_sources"}
        last_history_row = max(
            (item for item in target_group_history_rows if item.normalized_visit_date is not None),
            key=lambda item: item.normalized_visit_date,
            default=None,
        )

        target_group_events = [
            {
                "source_type": item.source_type,
                "source_file_name": item.source_file_name,
                "source_sheet_name": item.source_sheet_name,
                "source_row_no": item.source_row_no,
                "raw_service_type": item.raw_service_type,
                "normalized_service_key": item.normalized_service_key,
                "visit_date": item.normalized_visit_date,
                "raw_result": item.raw_result,
                "raw_hospital": item.raw_hospital,
                "raw_doctor": item.raw_doctor,
                "raw_note": item.raw_note,
            }
            for item in sorted(
                target_group_history_rows,
                key=lambda row: (row.normalized_visit_date is None, row.normalized_visit_date),
                reverse=True,
            )[:20]
        ]
        provenance_details = [
            {
                "source_file_id": str(item.source_file_id) if item.source_file_id else None,
                "source_file_name": item.source_file_name,
                "source_sheet_name": (item.raw_json or {}).get("source_sheet_name"),
                "source_row_no": item.source_row_no,
                "row_no": item.row_no,
                "match_method": item.match_method,
                "match_status": item.match_status,
                "warning_message": item.warning_message,
                "error_message": item.error_message,
            }
            for item in target_rows
        ]
        # Phase D: use stored link fields when present (generated after Phase D migration).
        # Fall back to recomputing from target_rows for pre-migration results.
        if result.person_link_status is not None:
            person_link_status = result.person_link_status
            duplicate_reason = result.duplicate_reason
            review_required = result.review_required
        else:
            person_link_status, duplicate_reason, review_required = (
                ResultGenerationService._person_link_details(target_rows) if target_rows else (None, None, False)
            )

        return GroupResultRowResponse(
            result_id=result.id,
            target_row_id=result.target_row_id,
            group_job_id=result.group_job_id,
            patient_id=result.patient_id,
            normalized_cid=result.normalized_cid,
            matched_identifier=matched_identifier,
            matched_name_basis=primary_row.matched_name_basis if primary_row else None,
            full_name=result.full_name,
            age=result.age,
            raw_age=primary_row.raw_age if primary_row else None,
            birth_date=primary_row.normalized_birth_date if primary_row else None,
            sex=result.sex,
            match_status=ResultGenerationService._match_status_for_result(result),
            match_method=primary_row.match_method if primary_row else None,
            match_confidence=primary_row.confidence_flag if primary_row else None,
            person_link_status=person_link_status,
            duplicate_reason=duplicate_reason,
            review_required=review_required,
            result_category=result.result_status,
            result_status=result.result_status,
            canonical_person_key=result.canonical_person_key,
            screening_status=screening_status,
            overdue_threshold_years=overdue_years,
            has_selected_service=result.has_selected_service,
            matching_record_count=result.matching_record_count,
            matched_service_keys=result.matched_service_keys or [],
            last_visit_date=result.last_visit_date,
            days_since_last_visit=result.days_since_last_visit,
            years_since_last_visit=float(result.years_since_last_visit) if result.years_since_last_visit is not None else None,
            target_group_history_labels=ResultGenerationService._first_non_empty([row.raw_target_history_labels for row in target_rows]),
            target_group_history_note=ResultGenerationService._merge_text_values([row.raw_target_history_note for row in target_rows]),
            target_group_history_last_visit_date=ResultGenerationService._latest_date(
                [row.normalized_target_history_last_visit_date for row in target_rows]
            ),
            history_found_in_screening_db=history_found_in_screening_db,
            history_found_in_target_group_file=history_found_in_target_group_file,
            history_source_summary=ResultGenerationService._history_source_summary_for_result(result.result_status),
            last_relevant_source=ResultGenerationService._last_relevant_source_for_response(result, last_history_row),
            latest_relevant_source_type=ResultGenerationService._last_relevant_source_for_response(result, last_history_row),
            target_group_nationality=ResultGenerationService._first_non_empty(
                [ResultGenerationService._read_target_group_raw_value(row, "nationality") for row in target_rows]
            ),
            target_group_address=ResultGenerationService._first_non_empty(
                [ResultGenerationService._read_target_group_raw_value(row, "address") for row in target_rows]
            ),
            source_file_id=primary_row.source_file_id if primary_row else None,
            source_file_name=primary_row.source_file_name if primary_row else None,
            source_sheet_name=(primary_row.raw_json or {}).get("source_sheet_name") if primary_row else None,
            source_row_no=primary_row.source_row_no if primary_row else None,
            source_origin_context="target_group_upload" if primary_row and (primary_row.source_file_name or primary_row.source_row_no is not None) else None,
            provenance_summary_count=len(target_rows),
            provenance_details=provenance_details,
            latest_source_file_name=last_history_row.source_file_name if ResultGenerationService._last_relevant_source_for_response(result, last_history_row) == "target_group_file" and last_history_row else None,
            latest_source_sheet_name=last_history_row.source_sheet_name if ResultGenerationService._last_relevant_source_for_response(result, last_history_row) == "target_group_file" and last_history_row else None,
            latest_source_row_no=last_history_row.source_row_no if ResultGenerationService._last_relevant_source_for_response(result, last_history_row) == "target_group_file" and last_history_row else None,
            screening_db_history_count=result.matching_record_count - len(target_group_history_rows) if history_found_in_screening_db and history_found_in_target_group_file else (result.matching_record_count if history_found_in_screening_db else 0),
            target_group_history_count=len(target_group_history_rows),
            target_group_history_events=target_group_events,
            warning_message=result.warning_message,
        )

    @staticmethod
    def _first_non_empty(values: list[str | None]) -> str | None:
        for value in values:
            if value:
                return value
        return None

    @staticmethod
    def _merge_text_values(values: list[str | None]) -> str | None:
        merged = []
        for value in values:
            if value and value not in merged:
                merged.append(value)
        return "; ".join(merged) if merged else None

    @staticmethod
    def _latest_date(values: list[date | None]) -> date | None:
        return max((value for value in values if value is not None), default=None)

    @staticmethod
    def _read_target_group_raw_value(target_row: TargetGroupRow | None, key: str) -> str | None:
        if target_row is None or not target_row.raw_json:
            return None
        value = target_row.raw_json.get(key)
        return str(value).strip() if value is not None and str(value).strip() else None

    @staticmethod
    def _query_filtered_result_ids(
        db: Session,
        group_id: UUID,
        overdue_years: int,
        view: str | None,
        query: str | None,
        overdue_enabled: bool,
        sort_col: str | None = None,
        sort_dir: str | None = None,
    ) -> list[UUID]:
        stmt = (
            select(TargetGroupResult.id)
            .select_from(TargetGroupResult)
            .outerjoin(TargetGroupRow, TargetGroupRow.id == TargetGroupResult.target_row_id)
            .where(TargetGroupResult.group_job_id == group_id)
        )
        stmt = ResultGenerationService._apply_results_filters(stmt, overdue_years, view=view, query=query, overdue_enabled=overdue_enabled)

        # Dynamic sort: allow client to specify sort column + direction.
        # Falls back to default (full_name ASC, id ASC) for unknown/missing columns.
        sortable = {
            "full_name": TargetGroupResult.full_name,
            "age": TargetGroupResult.age,
            "last_visit_date": TargetGroupResult.last_visit_date,
            "days_since_last_visit": TargetGroupResult.days_since_last_visit,
            "years_since_last_visit": TargetGroupResult.years_since_last_visit,
            "screening_status": TargetGroupResult.result_status,
            "matching_record_count": TargetGroupResult.matching_record_count,
        }
        col = sortable.get(sort_col or "")
        if col is not None:
            desc_order = (sort_dir or "asc").lower() == "desc"
            primary = col.desc().nullslast() if desc_order else col.asc().nullslast()
        else:
            primary = TargetGroupResult.full_name.asc().nullslast()
        stmt = stmt.order_by(primary, TargetGroupResult.id.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def _apply_results_filters(stmt, overdue_years: int, view: str | None, query: str | None, overdue_enabled: bool):
        special_result_statuses = tuple(NON_HISTORY_SCREENING_STATUSES)

        if view and view != "all":
            if view in {
                "invalid_identifier",
                "missing_identifier",
                "needs_review",
                "review_required_identity",
                "non_thai_nationality",
                "insufficient_identity_data",
            }:
                stmt = stmt.where(TargetGroupResult.result_status == view)
            elif view == "outside_target_scope":
                stmt = stmt.where(TargetGroupResult.result_status.in_(OUTSIDE_SCOPE_RESULT_STATUSES))
            elif view == "review_required":
                # Phase D: filter by stored review_required flag
                stmt = stmt.where(TargetGroupResult.review_required.is_(True))
            elif view == "never_checked":
                stmt = stmt.where(
                    TargetGroupResult.result_status.not_in(special_result_statuses),
                    TargetGroupResult.has_selected_service.is_(False),
                )
            elif view == "checked_but_overdue":
                stmt = stmt.where(
                    TargetGroupResult.result_status.not_in(special_result_statuses),
                    TargetGroupResult.has_selected_service.is_(True),
                    TargetGroupResult.years_since_last_visit >= Decimal(str(overdue_years)),
                )
            elif view == "checked_and_within_threshold":
                stmt = stmt.where(
                    TargetGroupResult.result_status.not_in(special_result_statuses),
                    TargetGroupResult.has_selected_service.is_(True),
                    TargetGroupResult.years_since_last_visit < Decimal(str(overdue_years)),
                )

        if overdue_enabled:
            stmt = stmt.where(
                TargetGroupResult.has_selected_service.is_(True),
                TargetGroupResult.years_since_last_visit >= Decimal(str(overdue_years)),
            )

        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(
                    TargetGroupResult.normalized_cid.ilike(pattern),
                    TargetGroupResult.full_name.ilike(pattern),
                    TargetGroupRow.matched_identifier_basis.ilike(pattern),
                    TargetGroupRow.matched_name_basis.ilike(pattern),
                    TargetGroupRow.source_file_name.ilike(pattern),
                    TargetGroupResult.warning_message.ilike(pattern),
                )
            )
        return stmt

    @staticmethod
    def _match_status_for_result(result: TargetGroupResult) -> str:
        if result.result_status in {"invalid_identifier", "missing_identifier"}:
            return "invalid"
        if result.result_status in {"needs_review", "review_required_identity", "insufficient_identity_data"}:
            return "needs_review"
        if result.result_status in OUTSIDE_SCOPE_RESULT_STATUSES:
            return "out_of_scope"
        return "matched" if result.has_selected_service else "not_found"

    @staticmethod
    def _normalize_selected_service_keys(disease_keys: list[str]) -> list[str]:
        return sorted({key.strip() for key in disease_keys if key and key.strip()})

    @staticmethod
    def _selection_hash(selected_service_keys: list[str]) -> str:
        joined = "|".join(selected_service_keys)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    @staticmethod
    def _can_reuse_existing_results(rows: list[TargetGroupResult], selected_service_hash: str) -> bool:
        return bool(rows) and all(row.selected_service_hash == selected_service_hash for row in rows)

    @staticmethod
    def _result_identifier_basis(row: TargetGroupRow) -> str | None:
        if row.match_method == "name_exact_secondary" and row.matched_identifier_basis:
            return row.matched_identifier_basis
        if row.matched_identifier_basis:
            return row.matched_identifier_basis
        return row.normalized_cid

    @staticmethod
    def _result_identifier_basis_for_rows(rows: list[TargetGroupRow]) -> str | None:
        for row in rows:
            basis = ResultGenerationService._result_identifier_basis(row)
            if basis:
                return basis
        return None

    @staticmethod
    def _find_target_group_history_matches(
        row: TargetGroupRow,
        history_by_identifier: dict[str, list[TargetGroupHistoryEvidence]],
        history_by_name_without_identifier: dict[str, list[TargetGroupHistoryEvidence]],
    ) -> list[TargetGroupHistoryEvidence]:
        return ResultGenerationService._collect_target_group_history_matches(
            [row],
            history_by_identifier,
            history_by_name_without_identifier,
        )

    @staticmethod
    def _history_source_summary_for_result(result_status: str) -> str:
        if result_status in {"invalid_identifier", "missing_identifier", "needs_review"}:
            return "no_history_found"
        if result_status == "screening_db_only":
            return "screening_db_only"
        if result_status == "target_group_file_only":
            return "target_group_file_only"
        if result_status == "both_sources":
            return "both_sources"
        return "no_history_found"

    @staticmethod
    def _last_relevant_source_for_response(
        result: TargetGroupResult,
        latest_target_group_history_row: TargetGroupHistoryEvidence | None,
    ) -> str | None:
        if result.result_status == "target_group_file_only":
            return "target_group_file"
        if result.result_status == "screening_db_only":
            return "screening_db"
        if result.result_status == "both_sources":
            if latest_target_group_history_row and result.last_visit_date == latest_target_group_history_row.normalized_visit_date:
                return "target_group_file"
            return "screening_db"
        return None

    @staticmethod
    def _result_category_for_rows(rows: list[TargetGroupRow], has_selected_service: bool) -> tuple[str, str | None]:
        warnings = [row.error_message or row.warning_message for row in rows if row.error_message or row.warning_message]

        if ResultGenerationService._is_non_thai_nationality(rows):
            return "non_thai_nationality", ResultGenerationService._merge_text_values(
                [*warnings, "แยกออกจากกลุ่มหลักเพราะสัญชาติไม่ใช่ไทย"]
            )

        if ResultGenerationService._is_explicitly_outside_target_scope(rows):
            return "outside_target_scope", ResultGenerationService._merge_text_values(
                [*warnings, "ข้อมูลถูกระบุว่าอยู่นอกขอบเขตกลุ่มเป้าหมาย"]
            )

        if any(row.cid_validation_status == "invalid_identifier" for row in rows):
            return "invalid_identifier", ResultGenerationService._merge_text_values(warnings)

        if all(row.cid_validation_status == "missing_identifier" for row in rows) and not any(
            row.normalized_full_name for row in rows
        ):
            return "missing_identifier", ResultGenerationService._merge_text_values(warnings)

        if not ResultGenerationService._has_identifier_eligible_scope(rows):
            if any(row.normalized_full_name for row in rows):
                return "review_required_identity", ResultGenerationService._merge_text_values(
                    [*warnings, "มีข้อมูลชื่อแต่ยังไม่พอสำหรับยืนยันตัวบุคคลอย่างปลอดภัย"]
                )
            return "insufficient_identity_data", ResultGenerationService._merge_text_values(
                [*warnings, "ข้อมูลระบุตัวตนไม่พอสำหรับคำนวณผลอย่างปลอดภัย"]
            )

        if any(row.match_status == "needs_review" for row in rows) and not has_selected_service:
            return "needs_review", ResultGenerationService._merge_text_values(warnings)

        if has_selected_service:
            return "screening_db_only", ResultGenerationService._merge_text_values(warnings)
        return "no_history_found", ResultGenerationService._merge_text_values(warnings)

    @staticmethod
    def _result_category_for_row(row: TargetGroupRow, has_selected_service: bool) -> tuple[str, str | None]:
        return ResultGenerationService._result_category_for_rows([row], has_selected_service)

    @staticmethod
    def _is_explicitly_outside_target_scope(rows: list[TargetGroupRow]) -> bool:
        outside_markers = {"outside_target_scope", "out_of_scope", "นอกขอบเขต", "นอกกลุ่มเป้าหมาย"}
        for row in rows:
            raw_json = row.raw_json or {}
            candidates = [
                raw_json.get("target_scope_status"),
                raw_json.get("scope_status"),
                raw_json.get("outside_target_scope"),
                raw_json.get("target_scope"),
            ]
            for candidate in candidates:
                normalized = normalize_text(candidate)
                if normalized and normalized.casefold() in outside_markers:
                    return True
        return False

    @staticmethod
    def _build_row_result_payload_for_rows(
        rows: list[TargetGroupRow],
        eligible_records: list[DiseaseScreeningRecord],
        eligible_history_rows: list[TargetGroupHistoryEvidence],
        record_key_to_selected_keys: dict[str, set[str]],
    ) -> dict:
        primary_row = rows[0]
        return ResultGenerationService._build_row_result_payload(
            primary_row,
            eligible_records,
            eligible_history_rows,
            record_key_to_selected_keys,
            grouped_rows=rows,
        )

    @staticmethod
    def _build_row_result_payload(
        row: TargetGroupRow,
        eligible_records: list[DiseaseScreeningRecord],
        eligible_history_rows: list[TargetGroupHistoryEvidence],
        record_key_to_selected_keys: dict[str, set[str]],
        grouped_rows: list[TargetGroupRow] | None = None,
    ) -> dict:
        rows = grouped_rows or [row]
        db_matched_service_keys = {
            selected_key
            for record in eligible_records
            for selected_key in record_key_to_selected_keys.get(record.normalized_service_key, {record.normalized_service_key})
        }
        tg_matched_service_keys = {
            selected_key
            for history_row in eligible_history_rows
            for selected_key in record_key_to_selected_keys.get(history_row.normalized_service_key or "", {history_row.normalized_service_key})
            if selected_key
        }
        matched_service_keys = sorted({*db_matched_service_keys, *tg_matched_service_keys})
        latest_db_visit = max((record.visit_date for record in eligible_records if record.visit_date is not None), default=None)
        # Exclude None visit dates — TG history rows can have normalized_visit_date=None
        # when the source cell was blank or unparseable. Including None in max() raises TypeError.
        latest_target_group_visit = max(
            (item.normalized_visit_date for item in eligible_history_rows if item.normalized_visit_date is not None),
            default=None,
        )
        latest_visit = max((value for value in [latest_db_visit, latest_target_group_visit] if value is not None), default=None)
        days_since, years_since = compute_visit_metrics(latest_visit)
        history_found_in_screening_db = bool(eligible_records)
        history_found_in_target_group_file = bool(eligible_history_rows)
        has_selected_service = history_found_in_screening_db or history_found_in_target_group_file
        result_category, warning_message = ResultGenerationService._result_category_for_rows(rows, has_selected_service)
        if result_category not in {
            "invalid_identifier",
            "missing_identifier",
            "needs_review",
            "review_required_identity",
            "non_thai_nationality",
            "outside_target_scope",
            "insufficient_identity_data",
        }:
            if history_found_in_screening_db and history_found_in_target_group_file:
                result_category = "both_sources"
            elif history_found_in_screening_db:
                result_category = "screening_db_only"
            elif history_found_in_target_group_file:
                result_category = "target_group_file_only"
            else:
                result_category = "no_history_found"

        warning_parts = [warning_message]
        if history_found_in_target_group_file and not history_found_in_screening_db:
            warning_parts.append("ใช้ประวัติจากไฟล์กลุ่มเป้าหมายเป็นหลัก เพราะยังไม่พบในฐานข้อมูลการตรวจโรค")
        if history_found_in_target_group_file and any(item.warning_message for item in eligible_history_rows):
            warning_parts.extend(item.warning_message for item in eligible_history_rows if item.warning_message)
        return {
            "has_selected_service": has_selected_service,
            "matching_record_count": len(eligible_records) + len(eligible_history_rows),
            "matched_service_keys": matched_service_keys,
            "last_visit_date": latest_visit,
            "days_since_last_visit": days_since,
            "years_since_last_visit": years_since,
            "result_status": result_category,
            "warning_message": "; ".join(part for part in warning_parts if part) or None,
        }

    @staticmethod
    def _screening_status_for_result(result: TargetGroupResult, overdue_years: int) -> str:
        if result.result_status in NON_HISTORY_SCREENING_STATUSES:
            return result.result_status
        if not result.has_selected_service:
            return "never_checked"
        if (result.years_since_last_visit or Decimal("0")) >= Decimal(str(overdue_years)):
            return "checked_but_overdue"
        return "checked_and_within_threshold"


    @staticmethod
    def _upsert_summary_cache(
        db: Session,
        summary: "ResultSummaryResponse",
        overdue_years: int,
        source_set_hash: str | None = None,
    ) -> None:
        """Write (or overwrite) the summary cache row for this group + service selection.

        Uses a dialect-aware INSERT ... ON CONFLICT DO UPDATE (via
        ``app.db.compat.make_upsert_stmt``) so the call is idempotent on both
        PostgreSQL and SQLite — re-generating the same group replaces the old
        cache row without leaving orphan rows.

        Supported dialects: PostgreSQL, SQLite (≥ 3.24.0 / Python ≥ 3.8).
        """
        service_hash = ResultGenerationService._selection_hash(summary.selected_service_keys)
        generated_at_value = summary.generated_at or func.now()
        values = dict(
            group_job_id=summary.group_job_id,
            selected_service_hash=service_hash,
            selected_service_keys=summary.selected_service_keys,
            overdue_threshold_years=overdue_years,
            total_target_people=summary.total_target_people,
            valid_identifier_people=summary.valid_identifier_people,
            invalid_identifier_people=summary.invalid_identifier_people,
            non_thai_nationality_people=summary.non_thai_nationality_people,
            insufficient_identity_people=summary.insufficient_identity_people,
            outside_target_scope_people=summary.outside_target_scope_people,
            review_required_identity_people=summary.review_required_identity_people,
            people_with_selected_history=summary.people_with_selected_history,
            people_without_selected_history=summary.people_without_selected_history,
            never_checked_people=summary.never_checked_people,
            checked_but_overdue_people=summary.checked_but_overdue_people,
            checked_and_within_threshold_people=summary.checked_and_within_threshold_people,
            coverage_percent=summary.coverage_percent,
            source_set_hash=source_set_hash,
            normalization_version=RESULT_NORMALIZATION_VERSION,
            generated_at=generated_at_value,
        )
        set_ = {
            "overdue_threshold_years": overdue_years,
            "total_target_people": summary.total_target_people,
            "valid_identifier_people": summary.valid_identifier_people,
            "invalid_identifier_people": summary.invalid_identifier_people,
            "non_thai_nationality_people": summary.non_thai_nationality_people,
            "insufficient_identity_people": summary.insufficient_identity_people,
            "outside_target_scope_people": summary.outside_target_scope_people,
            "review_required_identity_people": summary.review_required_identity_people,
            "people_with_selected_history": summary.people_with_selected_history,
            "people_without_selected_history": summary.people_without_selected_history,
            "never_checked_people": summary.never_checked_people,
            "checked_but_overdue_people": summary.checked_but_overdue_people,
            "checked_and_within_threshold_people": summary.checked_and_within_threshold_people,
            "coverage_percent": summary.coverage_percent,
            "source_set_hash": source_set_hash,
            "normalization_version": RESULT_NORMALIZATION_VERSION,
            "generated_at": generated_at_value,
        }
        stmt = _make_upsert_stmt(
            db,
            TargetGroupResultSummary,
            values=values,
            index_elements=["group_job_id", "selected_service_hash"],
            set_=set_,
        )
        db.execute(stmt)

    @staticmethod
    def _build_summary_from_sql(
        db: Session,
        group_id: UUID,
        overdue_years: int,
    ) -> ResultSummaryResponse | None:
        """Single-query aggregate summary.

        Replaces the pattern of loading every TargetGroupResult row into Python
        just to count them.  Uses SQL CASE expressions so the database does all
        the counting in one round trip.

        Returns None if no results exist for this group yet.
        """
        EXCLUDED = tuple(IDENTITY_EXCLUDED_RESULT_STATUSES)
        NON_HISTORY = tuple(NON_HISTORY_SCREENING_STATUSES)
        overdue_dec = Decimal(str(overdue_years))

        row = db.execute(
            select(
                func.count().label("total"),
                func.max(TargetGroupResult.generated_at).label("generated_at"),
                # identity breakdown
                func.sum(case(
                    (TargetGroupResult.result_status.in_(["invalid_identifier", "missing_identifier"]), 1),
                    else_=0,
                )).label("invalid_identifier_people"),
                func.sum(case(
                    (TargetGroupResult.result_status == "non_thai_nationality", 1),
                    else_=0,
                )).label("non_thai_nationality_people"),
                func.sum(case(
                    (TargetGroupResult.result_status == "insufficient_identity_data", 1),
                    else_=0,
                )).label("insufficient_identity_people"),
                func.sum(case(
                    (TargetGroupResult.result_status == "review_required_identity", 1),
                    else_=0,
                )).label("review_required_identity_people"),
                func.sum(case(
                    (TargetGroupResult.result_status == "outside_target_scope", 1),
                    else_=0,
                )).label("outside_target_scope_people"),
                func.sum(case(
                    (TargetGroupResult.result_status.not_in(list(EXCLUDED)), 1),
                    else_=0,
                )).label("valid_identifier_people"),
                # history breakdown (only for in-scope people)
                func.sum(case(
                    (TargetGroupResult.result_status.not_in(list(EXCLUDED)) & (TargetGroupResult.has_selected_service == True), 1),
                    else_=0,
                )).label("people_with_selected_history"),
                func.sum(case(
                    (TargetGroupResult.result_status.not_in(list(EXCLUDED)) & (TargetGroupResult.has_selected_service == False), 1),
                    else_=0,
                )).label("people_without_selected_history"),
                # screening status breakdown
                func.sum(case(
                    (TargetGroupResult.result_status.not_in(list(NON_HISTORY)) & (TargetGroupResult.has_selected_service == False), 1),
                    else_=0,
                )).label("never_checked_people"),
                func.sum(case(
                    (
                        TargetGroupResult.result_status.not_in(list(NON_HISTORY))
                        & (TargetGroupResult.has_selected_service == True)
                        & (TargetGroupResult.years_since_last_visit >= overdue_dec),
                        1,
                    ),
                    else_=0,
                )).label("checked_but_overdue_people"),
                func.sum(case(
                    (
                        TargetGroupResult.result_status.not_in(list(NON_HISTORY))
                        & (TargetGroupResult.has_selected_service == True)
                        & (TargetGroupResult.years_since_last_visit < overdue_dec),
                        1,
                    ),
                    else_=0,
                )).label("checked_and_within_threshold_people"),
            ).where(TargetGroupResult.group_job_id == group_id)
        ).one()

        if not row.total:
            return None

        selected_service_keys = db.scalar(
            select(TargetGroupResult.selected_service_keys)
            .where(TargetGroupResult.group_job_id == group_id)
            .order_by(TargetGroupResult.generated_at.desc())
            .limit(1)
        ) or []
        valid = int(row.valid_identifier_people or 0)
        with_history = int(row.people_with_selected_history or 0)
        coverage_percent = round((with_history / valid) * 100, 2) if valid else 0.0

        return ResultSummaryResponse(
            group_job_id=group_id,
            total_target_people=int(row.total),
            valid_identifier_people=valid,
            invalid_identifier_people=int(row.invalid_identifier_people or 0),
            non_thai_nationality_people=int(row.non_thai_nationality_people or 0),
            insufficient_identity_people=int(row.insufficient_identity_people or 0),
            outside_target_scope_people=int(row.outside_target_scope_people or 0),
            review_required_identity_people=int(row.review_required_identity_people or 0),
            people_with_selected_history=with_history,
            people_without_selected_history=int(row.people_without_selected_history or 0),
            never_checked_people=int(row.never_checked_people or 0),
            checked_but_overdue_people=int(row.checked_but_overdue_people or 0),
            checked_and_within_threshold_people=int(row.checked_and_within_threshold_people or 0),
            coverage_percent=coverage_percent,
            coverage_denominator_people=valid,
            overdue_threshold_years=overdue_years,
            selected_service_count=len(selected_service_keys),
            selected_service_keys=selected_service_keys,
            generated_at=row.generated_at,
        )

    @staticmethod
    def _build_summary(
        rows: list[TargetGroupResult],
        selected_service_keys: list[str],
        generated_at: datetime | None,
        overdue_years: int,
        source_set_hash: str | None = None,
    ) -> ResultSummaryResponse:
        total_target_people = len(rows)
        invalid_identifier_people = sum(1 for row in rows if row.result_status in {"invalid_identifier", "missing_identifier"})
        non_thai_nationality_people = sum(1 for row in rows if row.result_status == "non_thai_nationality")
        insufficient_identity_people = sum(1 for row in rows if row.result_status == "insufficient_identity_data")
        review_required_identity_people = sum(1 for row in rows if row.result_status == "review_required_identity")
        outside_target_scope_people = sum(1 for row in rows if row.result_status == "outside_target_scope")
        valid_identifier_people = sum(
            1
            for row in rows
            if row.result_status
            not in {
                "invalid_identifier",
                "missing_identifier",
                "insufficient_identity_data",
                "review_required_identity",
                *OUTSIDE_SCOPE_RESULT_STATUSES,
            }
        )
        people_with_selected_history = sum(
            1
            for row in rows
            if row.result_status not in IDENTITY_EXCLUDED_RESULT_STATUSES and row.has_selected_service
        )
        people_without_selected_history = sum(
            1
            for row in rows
            if row.result_status not in IDENTITY_EXCLUDED_RESULT_STATUSES and not row.has_selected_service
        )
        never_checked_people = sum(
            1
            for row in rows
            if ResultGenerationService._screening_status_for_result(row, overdue_years) == "never_checked"
        )
        checked_but_overdue_people = sum(
            1
            for row in rows
            if ResultGenerationService._screening_status_for_result(row, overdue_years) == "checked_but_overdue"
        )
        checked_and_within_threshold_people = sum(
            1
            for row in rows
            if ResultGenerationService._screening_status_for_result(row, overdue_years) == "checked_and_within_threshold"
        )
        coverage_percent = round((people_with_selected_history / valid_identifier_people) * 100, 2) if valid_identifier_people else 0.0
        return ResultSummaryResponse(
            group_job_id=rows[0].group_job_id,
            total_target_people=total_target_people,
            valid_identifier_people=valid_identifier_people,
            invalid_identifier_people=invalid_identifier_people,
            non_thai_nationality_people=non_thai_nationality_people,
            insufficient_identity_people=insufficient_identity_people,
            outside_target_scope_people=outside_target_scope_people,
            review_required_identity_people=review_required_identity_people,
            people_with_selected_history=people_with_selected_history,
            people_without_selected_history=people_without_selected_history,
            never_checked_people=never_checked_people,
            checked_but_overdue_people=checked_but_overdue_people,
            checked_and_within_threshold_people=checked_and_within_threshold_people,
            coverage_percent=coverage_percent,
            coverage_denominator_people=valid_identifier_people,
            overdue_threshold_years=overdue_years,
            selected_service_count=len(selected_service_keys),
            selected_service_keys=selected_service_keys,
            generated_at=generated_at,
            generated_source_set_hash=source_set_hash,
        )

    @staticmethod
    def _build_breakdown_from_screening(
        db: Session,
        rows: list[TargetGroupResult],
        selected_service_keys: list[str],
    ) -> list[ServiceBreakdownResponse]:
        if not rows:
            return []
        group_id = rows[0].group_job_id
        mapping_rows = db.scalars(
            select(DiseaseMapping).where(DiseaseMapping.normalized_key.in_(selected_service_keys))
        ).all()
        _, record_key_to_selected_keys = ResultGenerationService._expand_selected_service_keys(
            mapping_rows,
            selected_service_keys,
        )
        eligible_record_keys = sorted(record_key_to_selected_keys)

        target_rows = db.scalars(
            select(TargetGroupRow)
            .where(TargetGroupRow.group_job_id == group_id)
            .order_by(TargetGroupRow.row_no.asc(), TargetGroupRow.created_at.asc())
        ).all()
        person_contexts = ResultGenerationService._build_person_contexts(target_rows)

        screening_records = db.scalars(
            select(DiseaseScreeningRecord).where(
                DiseaseScreeningRecord.normalized_service_key.in_(eligible_record_keys)
            )
        ).all()
        screening_by_identifier: dict[str, list[DiseaseScreeningRecord]] = defaultdict(list)
        for record in screening_records:
            screening_by_identifier[record.normalized_person_identifier].append(record)

        history_rows = ResultGenerationService._load_selected_target_group_history_rows(db, group_id, eligible_record_keys)
        history_by_identifier, history_by_name_without_identifier = ResultGenerationService._index_target_group_history_rows(history_rows)

        per_service_people: dict[str, set[str]] = {key: set() for key in selected_service_keys}
        per_service_count: dict[str, int] = {key: 0 for key in selected_service_keys}

        for context in person_contexts:
            identifier_basis = ResultGenerationService._result_identifier_basis_for_rows(context.rows)
            eligible_records = ResultGenerationService._collect_screening_records_for_rows(context.rows, screening_by_identifier)
            eligible_history_rows = ResultGenerationService._collect_target_group_history_matches(
                context.rows,
                history_by_identifier,
                history_by_name_without_identifier,
            )
            for record in eligible_records:
                for selected_key in record_key_to_selected_keys.get(record.normalized_service_key, {record.normalized_service_key}):
                    per_service_count[selected_key] += 1
                    if identifier_basis:
                        per_service_people[selected_key].add(identifier_basis)
            for history_row in eligible_history_rows:
                history_identifier = history_row.normalized_cid or history_row.normalized_full_name or identifier_basis
                if not history_identifier:
                    continue
                for selected_key in record_key_to_selected_keys.get(history_row.normalized_service_key or "", {history_row.normalized_service_key}):
                    if not selected_key:
                        continue
                    per_service_count[selected_key] += 1
                    per_service_people[selected_key].add(history_identifier)

        return [
            ServiceBreakdownResponse(
                selected_service_key=service_key,
                distinct_people_count=len(per_service_people[service_key]),
                matching_record_count=per_service_count[service_key],
            )
            for service_key in selected_service_keys
        ]

    @staticmethod
    def _expand_selected_service_keys(
        mapping_rows: list[DiseaseMapping],
        selected_service_keys: list[str],
    ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        selected_to_record_keys: dict[str, set[str]] = {key: {key} for key in selected_service_keys}

        # Expand via DiseaseMapping raw_name aliases (slugified)
        for row in mapping_rows:
            if row.raw_name:
                normalized_alias = normalize_service_key(row.raw_name).normalized_value
                if normalized_alias:
                    selected_to_record_keys.setdefault(row.normalized_key, {row.normalized_key}).add(normalized_alias)

        if "cervical_screen" in selected_service_keys:
            selected_to_record_keys.setdefault("cervical_screen", {"cervical_screen"}).update(
                {"pap_smear", "via", "hpv", "other_method"}
            )

        # Expand using the Thai-slug → canonical mapping table so that history
        # rows that were imported BEFORE the field_mapping_service fix (and
        # therefore stored an un-remapped Thai slug as normalized_service_key)
        # are still included in the result query.
        # We invert the table: for each canonical key that is selected, add
        # every Thai slug that maps to it as an additional eligible record key.
        for thai_slug, canonical in _THAI_SERVICE_SLUG_TO_CANONICAL.items():
            if canonical in selected_to_record_keys and thai_slug not in selected_to_record_keys[canonical]:
                selected_to_record_keys[canonical].add(thai_slug)

        record_key_to_selected_keys: dict[str, set[str]] = defaultdict(set)
        for selected_key, record_keys in selected_to_record_keys.items():
            for record_key in record_keys:
                record_key_to_selected_keys[record_key].add(selected_key)
        return selected_to_record_keys, record_key_to_selected_keys
