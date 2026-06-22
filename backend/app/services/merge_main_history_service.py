from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.diagnosis_history import DiagnosisHistory
from app.models.disease_screening_record import DiseaseScreeningRecord
from app.models.patient import Patient
from app.models.staging_history_record import StagingHistoryRecord
from app.utils.text_normalization import normalize_name


@dataclass
class MergeSummary:
    patient_count: int = 0
    history_count: int = 0
    merged_rows: int = 0
    skipped_rows: int = 0
    duplicate_identifier_count: int = 0


class MergeMainHistoryService:
    @staticmethod
    def merge_import_job(db: Session, import_job_id) -> MergeSummary:
        staging_rows = db.scalars(
            select(StagingHistoryRecord).where(StagingHistoryRecord.import_job_id == import_job_id)
        ).all()

        mergeable_rows = MergeMainHistoryService._deduplicate_rows(
            [row for row in staging_rows if MergeMainHistoryService.is_mergeable_row(row)]
        )
        skipped_rows = len(staging_rows) - len(mergeable_rows)
        if not mergeable_rows:
            raise ValueError("ไม่พบแถวที่ผ่านเกณฑ์สำหรับ merge เข้าฐานข้อมูลการตรวจโรค")

        identifier_counter = Counter(
            row.normalized_person_identifier for row in mergeable_rows if row.normalized_person_identifier
        )
        duplicate_identifier_count = sum(count for count in identifier_counter.values() if count > 1)

        # Hospital-safe MVP: replace production snapshot only after staging validated.
        db.execute(delete(DiseaseScreeningRecord))
        db.execute(delete(DiagnosisHistory))
        db.execute(delete(Patient))
        db.flush()

        patient_index: dict[tuple[str, str], Patient] = {}
        summary = MergeSummary(
            skipped_rows=skipped_rows,
            duplicate_identifier_count=duplicate_identifier_count,
        )

        for row in mergeable_rows:
            db.add(MergeMainHistoryService._build_disease_screening_record(row, import_job_id))
            summary.merged_rows += 1

            patient, created = MergeMainHistoryService._resolve_or_create_patient(db, patient_index, row, import_job_id)
            if created:
                summary.patient_count += 1

            db.add(
                DiagnosisHistory(
                    patient_id=patient.id,
                    visit_date=row.normalized_visit_date,
                    raw_person_identifier=row.raw_person_identifier,
                    diagnosis_code=row.normalized_diagnosis_code,
                    diagnosis_name=row.normalized_diagnosis_name,
                    raw_service_type=row.raw_service_type,
                    normalized_person_identifier=row.normalized_person_identifier,
                    normalized_service_key=row.normalized_service_key or row.normalized_disease_key,
                    normalized_disease_key=row.normalized_disease_key,
                    department=row.raw_department,
                    doctor_name=row.raw_doctor_name,
                    source_import_job_id=import_job_id,
                    source_file_id=row.source_file_id,
                    source_file_name=row.source_file_name,
                    source_row_no=row.source_row_no or row.row_no,
                )
            )
            summary.history_count += 1

        db.flush()
        return summary

    @staticmethod
    def is_mergeable_row(row: StagingHistoryRecord) -> bool:
        return (
            row.parse_status == "parsed"
            and row.validation_status in {"valid", "warning"}
            and bool(row.raw_person_identifier)
            and bool(row.normalized_person_identifier)
            and bool(row.raw_service_type)
            and bool(row.normalized_service_key)
            and row.normalized_visit_date is not None
        )

    @staticmethod
    def _deduplicate_rows(rows: list[StagingHistoryRecord]) -> list[StagingHistoryRecord]:
        seen: set[tuple[object, object, object]] = set()
        deduped: list[StagingHistoryRecord] = []
        for row in rows:
            key = (row.import_job_id, row.source_file_id, row.source_row_no or row.row_no)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    @staticmethod
    def _build_disease_screening_record(row: StagingHistoryRecord, import_job_id) -> DiseaseScreeningRecord:
        return DiseaseScreeningRecord(
            source_import_job_id=import_job_id,
            source_file_id=row.source_file_id,
            source_file_name=row.source_file_name,
            source_row_no=row.source_row_no or row.row_no,
            raw_person_identifier=row.raw_person_identifier,
            normalized_person_identifier=row.normalized_person_identifier,
            full_name=row.raw_full_name,
            normalized_full_name=row.normalized_full_name,
            raw_service_type=row.raw_service_type,
            normalized_service_key=row.normalized_service_key,
            visit_date=row.normalized_visit_date,
            hcode=row.raw_hcode,
            transaction_id=row.raw_transaction_id,
            rep_no=row.raw_rep_no,
        )

    @staticmethod
    def _resolve_or_create_patient(
        db: Session,
        patient_index: dict[tuple[str, str], Patient],
        row: StagingHistoryRecord,
        import_job_id,
    ) -> tuple[Patient, bool]:
        candidate_keys = list(MergeMainHistoryService._patient_candidate_keys(row))
        for candidate in candidate_keys:
            cached = patient_index.get(candidate)
            if cached is not None:
                return cached, False

        patient = Patient(
            pid=row.normalized_pid,
            citizen_id=row.normalized_citizen_id,
            hn=row.normalized_hn,
            full_name=row.normalized_full_name or row.raw_full_name or "UNKNOWN",
            birth_date=row.normalized_birth_date,
            source_import_job_id=import_job_id,
        )
        db.add(patient)
        db.flush()
        for candidate in candidate_keys:
            patient_index[candidate] = patient
        return patient, True

    @staticmethod
    def _patient_candidate_keys(row: StagingHistoryRecord) -> Iterable[tuple[str, str]]:
        if row.normalized_pid:
            yield ("pid", row.normalized_pid)
        if row.normalized_citizen_id:
            yield ("citizen_id", row.normalized_citizen_id)
        if row.normalized_hn:
            yield ("hn", row.normalized_hn)
        if row.normalized_full_name and row.normalized_birth_date:
            yield ("name_birth", f"{normalize_name(row.normalized_full_name)}|{row.normalized_birth_date.isoformat()}")
        if row.normalized_full_name:
            normalized_name = normalize_name(row.normalized_full_name)
            if normalized_name:
                yield ("name", normalized_name)
