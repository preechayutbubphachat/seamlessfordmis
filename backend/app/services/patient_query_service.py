from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.diagnosis_history import DiagnosisHistory
from app.models.disease_mapping import DiseaseMapping
from app.models.disease_screening_record import DiseaseScreeningRecord
from app.models.patient import Patient
from app.models.target_group_history_row import TargetGroupHistoryRow
from app.models.target_group_result import TargetGroupResult
from app.schemas.patient import (
    DiagnosisHistoryResponse,
    PatientHistoryResponse,
    PatientSummaryResponse,
    ResultSourceHistoryResponse,
    ScreeningRecordResponse,
)


class PatientQueryService:
    @staticmethod
    def search(db: Session, query: str) -> list[PatientSummaryResponse]:
        pattern = f"%{query.strip()}%"
        rows = db.scalars(
            select(Patient).where(
                or_(
                    Patient.pid.ilike(pattern),
                    Patient.citizen_id.ilike(pattern),
                    Patient.hn.ilike(pattern),
                    Patient.full_name.ilike(pattern),
                )
            )
        ).all()
        return [
            PatientSummaryResponse(
                id=row.id,
                pid=row.pid,
                citizen_id=row.citizen_id,
                hn=row.hn,
                full_name=row.full_name,
                birth_date=row.birth_date,
            )
            for row in rows
        ]

    @staticmethod
    def history(db: Session, patient_id: UUID) -> PatientHistoryResponse:
        """Return patient identity + screening history from DiseaseScreeningRecord.

        DiseaseScreeningRecord is the new import-pipeline table (Phase 2+).
        DiagnosisHistory is kept for legacy display but is not authoritative.
        We query DiseaseScreeningRecord first; if no records exist we fall back
        to DiagnosisHistory so that data imported before the pipeline upgrade
        remains visible.
        """
        patient = db.get(Patient, patient_id)
        if patient is None:
            raise ValueError("ไม่พบผู้ป่วย")

        patient_summary = PatientSummaryResponse(
            id=patient.id,
            pid=patient.pid,
            citizen_id=patient.citizen_id,
            hn=patient.hn,
            full_name=patient.full_name,
            birth_date=patient.birth_date,
        )

        # Try the new pipeline table first, matching on the patient's
        # normalized identifier (citizen_id or pid, whichever is present).
        normalized_id = patient.citizen_id or patient.pid
        if normalized_id:
            screening_rows = db.scalars(
                select(DiseaseScreeningRecord)
                .where(DiseaseScreeningRecord.normalized_person_identifier == normalized_id)
                .order_by(DiseaseScreeningRecord.visit_date.desc())
            ).all()
            if screening_rows:
                return PatientHistoryResponse(
                    patient=patient_summary,
                    history=[
                        DiagnosisHistoryResponse(
                            visit_date=record.visit_date,
                            diagnosis_code=None,
                            diagnosis_name=record.raw_service_type,
                            normalized_disease_key=record.normalized_service_key,
                            department=None,
                            doctor_name=None,
                        )
                        for record in screening_rows
                    ],
                )

        # Legacy fallback — DiagnosisHistory table (pre-pipeline data).
        history_rows = db.scalars(
            select(DiagnosisHistory)
            .where(DiagnosisHistory.patient_id == patient_id)
            .order_by(DiagnosisHistory.visit_date.desc())
        ).all()
        return PatientHistoryResponse(
            patient=patient_summary,
            history=[
                DiagnosisHistoryResponse(
                    visit_date=item.visit_date,
                    diagnosis_code=item.diagnosis_code,
                    diagnosis_name=item.diagnosis_name,
                    normalized_disease_key=item.normalized_disease_key,
                    department=item.department,
                    doctor_name=item.doctor_name,
                )
                for item in history_rows
            ],
        )

    @staticmethod
    def source_history_for_result(
        db: Session,
        result_id: UUID,
        selected_service_keys: list[str] | None = None,
    ) -> ResultSourceHistoryResponse:
        """Return both evidence sources for one target group result row.

        This endpoint supports the patient-detail modal for Phase C so the UI
        can show:
        - screening DB records (DiseaseScreeningRecord) for this person
        - target-group-file history events already stored in TargetGroupHistoryRow

        When selected_service_keys is provided the screening records are filtered
        to only those service keys (matching the generate() call).  When omitted,
        all screening records for the person are returned.

        Works even when patient_id is NULL (TG-file-only person) as long as
        normalized_cid is available.
        """
        result = db.get(TargetGroupResult, result_id)
        if result is None:
            raise ValueError("ไม่พบผลลัพธ์")

        normalized_cid = result.normalized_cid

        # --- Screening DB records ---
        screening_records: list[DiseaseScreeningRecord] = []
        if normalized_cid:
            stmt = select(DiseaseScreeningRecord).where(
                DiseaseScreeningRecord.normalized_person_identifier == normalized_cid
            )
            if selected_service_keys:
                stmt = stmt.where(
                    DiseaseScreeningRecord.normalized_service_key.in_(selected_service_keys)
                )
            screening_records = list(
                db.scalars(stmt.order_by(DiseaseScreeningRecord.visit_date.desc())).all()
            )

        screening_responses = [
            ScreeningRecordResponse(
                record_id=record.id,
                source_file_name=record.source_file_name,
                source_row_no=record.source_row_no,
                normalized_person_identifier=record.normalized_person_identifier,
                full_name=record.full_name,
                raw_service_type=record.raw_service_type,
                normalized_service_key=record.normalized_service_key,
                visit_date=record.visit_date,
            )
            for record in screening_records
        ]

        # --- TG file history rows ---
        # Expand selected_service_keys the same way result_generation_service does:
        # pre-fix imports stored Thai slugs (e.g. "ตรวจมะเร็งปากมดลูก") instead of
        # the canonical key ("cervical_screen").  _expand_selected_service_keys()
        # inverts _THAI_SERVICE_SLUG_TO_CANONICAL and adds cervical sub-keys so
        # those older rows are still visible here.
        tg_eligible_keys: list[str] | None = None
        if selected_service_keys:
            from app.services.result_generation_service import ResultGenerationService
            mapping_rows = db.scalars(
                select(DiseaseMapping).where(DiseaseMapping.normalized_key.in_(selected_service_keys))
            ).all()
            _, record_key_to_selected = ResultGenerationService._expand_selected_service_keys(
                list(mapping_rows), selected_service_keys
            )
            tg_eligible_keys = sorted(record_key_to_selected) or selected_service_keys

        tg_rows: list[TargetGroupHistoryRow] = []
        if normalized_cid:
            tg_stmt = select(TargetGroupHistoryRow).where(
                TargetGroupHistoryRow.group_job_id == result.group_job_id,
                TargetGroupHistoryRow.normalized_cid == normalized_cid,
            )
            if tg_eligible_keys:
                tg_stmt = tg_stmt.where(
                    TargetGroupHistoryRow.normalized_service_key.in_(tg_eligible_keys)
                )
            tg_rows = list(
                db.scalars(
                    tg_stmt.order_by(TargetGroupHistoryRow.normalized_visit_date.desc().nullslast())
                ).all()
            )

        tg_events = [
            {
                "source_type": "target_group_history_sheet",
                "source_file_name": row.source_file_name,
                "source_sheet_name": row.source_sheet_name,
                "source_row_no": row.source_row_no,
                "raw_service_type": row.raw_service_type,
                "normalized_service_key": row.normalized_service_key,
                "visit_date": row.normalized_visit_date.isoformat() if row.normalized_visit_date else None,
                "raw_result": row.raw_result,
                "raw_hospital": row.raw_hospital,
                "raw_doctor": row.raw_doctor,
                "raw_note": row.raw_note,
                "validation_status": row.validation_status,
                "warning_message": row.warning_message,
            }
            for row in sorted(
                tg_rows,
                key=lambda r: (r.normalized_visit_date is None, r.normalized_visit_date),
                reverse=True,
            )
        ]

        # Determine summary
        has_db = bool(screening_responses)
        has_tg = bool(tg_events)
        if has_db and has_tg:
            summary = "both_sources"
        elif has_db:
            summary = "screening_db_only"
        elif has_tg:
            summary = "target_group_file_only"
        else:
            summary = "no_history_found"

        return ResultSourceHistoryResponse(
            result_id=result_id,
            normalized_cid=normalized_cid,
            full_name=result.full_name,
            screening_db_records=screening_responses,
            target_group_history_events=tg_events,
            history_source_summary=summary,
        )
