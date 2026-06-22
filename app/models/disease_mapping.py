from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class DiseaseMapping(TimestampMixin, Base):
    __tablename__ = "disease_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Multiple source service-item names may map to the same normalized group.
    normalized_disease_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    diagnosis_code: Mapped[str | None] = mapped_column(String(50), index=True)
    disease_name_raw: Mapped[str | None] = mapped_column(String(255), index=True)
    disease_group_label: Mapped[str] = mapped_column(String(255), nullable=False)
    group_type: Mapped[str] = mapped_column(String(30), nullable=False, default="service", index=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
