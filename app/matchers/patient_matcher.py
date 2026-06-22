from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.target_group import MatchMethod, MatchStatus, TargetGroupRow
from app.utils.normalizers import normalize_name


class PatientMatcher:
    @staticmethod
    def match_row(db: Session, row: TargetGroupRow) -> tuple[Patient | None, MatchMethod, MatchStatus, list[dict]]:
        flags: list[dict] = []

        if row.pid:
            patient = db.scalar(select(Patient).where(Patient.pid == row.pid))
            if patient:
                return patient, MatchMethod.pid, MatchStatus.matched, flags

        if row.citizen_id:
            patient = db.scalar(select(Patient).where(Patient.citizen_id == row.citizen_id))
            if patient:
                return patient, MatchMethod.citizen_id, MatchStatus.matched, flags

        if row.hn:
            patient = db.scalar(select(Patient).where(Patient.hn == row.hn))
            if patient:
                return patient, MatchMethod.hn, MatchStatus.matched, flags

        if row.full_name and row.birth_date:
            exact_matches = db.scalars(
                select(Patient).where(
                    Patient.normalized_name == normalize_name(row.full_name),
                    Patient.birth_date == row.birth_date,
                )
            ).all()
            if len(exact_matches) == 1:
                return exact_matches[0], MatchMethod.name_birth_date, MatchStatus.matched, flags
            if len(exact_matches) > 1:
                flags.append({"code": "ambiguous_name_birth_date", "message": "Multiple patients share name and birth date"})
                return None, MatchMethod.name_birth_date, MatchStatus.ambiguous, flags

        if row.full_name:
            name_matches = db.scalars(select(Patient).where(Patient.normalized_name == normalize_name(row.full_name))).all()
            if len(name_matches) == 1:
                flags.append({"code": "name_only_review", "message": "Name-only matches must be reviewed manually"})
                return name_matches[0], MatchMethod.name_only, MatchStatus.needs_review, flags
            if len(name_matches) > 1:
                flags.append({"code": "ambiguous_name_only", "message": "Multiple patients found by name only"})
                return None, MatchMethod.name_only, MatchStatus.ambiguous, flags

        return None, MatchMethod.unmatched, MatchStatus.unmatched, flags
