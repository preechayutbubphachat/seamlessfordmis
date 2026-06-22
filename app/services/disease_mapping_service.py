from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.disease_mapping import DiseaseMapping
from app.utils.normalizers import normalize_identifier, normalize_text


class DiseaseMappingService:
    @staticmethod
    def _candidate_diagnosis_codes(diagnosis_code: str | None) -> list[str]:
        if not diagnosis_code:
            return []

        raw_text = str(diagnosis_code)
        candidates: list[str] = []
        direct = normalize_identifier(raw_text)
        if direct:
            candidates.append(direct)

        token = ""
        for char in raw_text:
            if char.isalnum():
                token += char
                continue
            normalized_token = normalize_identifier(token)
            if normalized_token and normalized_token not in candidates:
                candidates.append(normalized_token)
            token = ""

        normalized_token = normalize_identifier(token)
        if normalized_token and normalized_token not in candidates:
            candidates.append(normalized_token)

        return candidates

    @staticmethod
    def resolve_disease_key(db: Session, diagnosis_code: str | None, disease_name_raw: str | None) -> str | None:
        normalized_name = normalize_text(disease_name_raw)

        for normalized_code in DiseaseMappingService._candidate_diagnosis_codes(diagnosis_code):
            mapping = db.scalar(
                select(DiseaseMapping).where(
                    DiseaseMapping.diagnosis_code == normalized_code,
                    DiseaseMapping.is_active.is_(True),
                )
            )
            if mapping:
                return mapping.normalized_disease_key

        if normalized_name:
            mapping = db.scalar(
                select(DiseaseMapping).where(
                    DiseaseMapping.disease_name_raw == normalized_name,
                    DiseaseMapping.is_active.is_(True),
                )
            )
            if mapping:
                return mapping.normalized_disease_key

        return None
