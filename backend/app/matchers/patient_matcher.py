from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.disease_screening_record import DiseaseScreeningRecord
from app.models.patient import Patient
from app.models.target_group_row import TargetGroupRow


@dataclass(frozen=True)
class MatchDecision:
    patient: Patient | None
    match_method: str
    match_status: str
    matched_identifier_basis: str | None = None
    matched_name_basis: str | None = None
    match_confidence: str = "low"


class PatientMatcher:
    @staticmethod
    def match(db: Session, row: TargetGroupRow) -> MatchDecision:
        normalized_cid = row.normalized_cid
        if normalized_cid:
            identifier_match = PatientMatcher._match_by_identifier(db, normalized_cid)
            if identifier_match is not None:
                return identifier_match

        return PatientMatcher._match_by_name_secondary(db, row)

    @staticmethod
    def _match_by_identifier(db: Session, normalized_cid: str) -> MatchDecision | None:
        screening_exists = db.scalar(
            select(DiseaseScreeningRecord.id).where(
                DiseaseScreeningRecord.normalized_person_identifier == normalized_cid
            ).limit(1)
        )
        if screening_exists is None:
            return None

        patient = PatientMatcher._resolve_patient_by_identifier(db, normalized_cid)
        return MatchDecision(
            patient=patient,
            match_method="identifier_exact",
            match_status="matched",
            matched_identifier_basis=normalized_cid,
            match_confidence="high" if patient else "medium",
        )

    @staticmethod
    def _match_by_name_secondary(db: Session, row: TargetGroupRow) -> MatchDecision:
        normalized_name = row.normalized_full_name
        if not normalized_name:
            return MatchDecision(
                patient=None,
                match_method="not_found",
                match_status="not_found",
                match_confidence="low",
            )

        name_records = db.scalars(
            select(DiseaseScreeningRecord).where(
                DiseaseScreeningRecord.normalized_full_name == normalized_name
            )
        ).all()
        distinct_identifiers = sorted(
            {
                record.normalized_person_identifier
                for record in name_records
                if record.normalized_person_identifier
            }
        )
        if not distinct_identifiers:
            return MatchDecision(
                patient=None,
                match_method="not_found",
                match_status="not_found",
                matched_name_basis=normalized_name,
                match_confidence="low",
            )
        if len(distinct_identifiers) > 1:
            return MatchDecision(
                patient=None,
                match_method="needs_review",
                match_status="needs_review",
                matched_name_basis=normalized_name,
                match_confidence="low",
            )

        matched_identifier = distinct_identifiers[0]
        patient = PatientMatcher._resolve_patient_by_identifier(db, matched_identifier)
        if patient is not None and PatientMatcher._has_identity_conflict(row, patient):
            return MatchDecision(
                patient=None,
                match_method="needs_review",
                match_status="needs_review",
                matched_identifier_basis=matched_identifier,
                matched_name_basis=normalized_name,
                match_confidence="low",
            )

        return MatchDecision(
            patient=patient,
            match_method="name_exact_secondary",
            match_status="matched",
            matched_identifier_basis=matched_identifier,
            matched_name_basis=normalized_name,
            match_confidence="medium" if patient else "low",
        )

    @staticmethod
    def _resolve_patient_by_identifier(db: Session, normalized_identifier: str) -> Patient | None:
        patient_candidates = db.scalars(
            select(Patient).where(
                or_(
                    Patient.citizen_id == normalized_identifier,
                    Patient.pid == normalized_identifier,
                )
            )
        ).all()
        deduped_by_id: dict[object, Patient] = {}
        for patient in patient_candidates:
            deduped_by_id[patient.id] = patient
        unique_patients = list(deduped_by_id.values())
        if len(unique_patients) == 1:
            return unique_patients[0]
        return None

    @staticmethod
    def _has_identity_conflict(row: TargetGroupRow, patient: Patient) -> bool:
        if row.normalized_birth_date and patient.birth_date and row.normalized_birth_date != patient.birth_date:
            return True
        if row.normalized_sex and patient.sex and row.normalized_sex != patient.sex:
            return True
        return False
