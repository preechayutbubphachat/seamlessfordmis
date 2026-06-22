from sqlalchemy import Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DiseaseMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disease_mapping"
    __table_args__ = (
        Index("idx_disease_mapping_raw_code", "raw_code"),
        Index("idx_disease_mapping_raw_name", "raw_name"),
        Index("idx_disease_mapping_normalized_key", "normalized_key"),
    )

    raw_code: Mapped[str | None] = mapped_column(Text)
    raw_name: Mapped[str | None] = mapped_column(Text, comment="ค่าโรคหรือ service item ดิบจากแหล่งข้อมูล")
    normalized_key: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_label: Mapped[str] = mapped_column(Text, nullable=False)
    icd10_code: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
