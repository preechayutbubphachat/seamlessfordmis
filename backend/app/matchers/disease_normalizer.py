from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.disease_mapping import DiseaseMapping
from app.utils.text_normalization import normalize_text


class DiseaseNormalizer:
    @staticmethod
    def resolve_key(db: Session, raw_code: str | None, raw_name: str | None) -> str | None:
        code = normalize_text(raw_code)
        name = normalize_text(raw_name)

        if code:
            match = db.scalar(select(DiseaseMapping).where(DiseaseMapping.raw_code == code, DiseaseMapping.is_active.is_(True)))
            if match:
                return match.normalized_key

        if name:
            match = db.scalar(select(DiseaseMapping).where(DiseaseMapping.raw_name == name, DiseaseMapping.is_active.is_(True)))
            if match:
                return match.normalized_key

        return None
