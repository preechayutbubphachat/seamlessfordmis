from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DiagnosisHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "diagnosis_history"
    __table_args__ = (
        Index("idx_diagnosis_history_patient_id", "patient_id"),
        Index("idx_diagnosis_history_visit_date", "visit_date"),
        Index("idx_diagnosis_history_diagnosis_code", "diagnosis_code"),
        Index("idx_diagnosis_history_disease_key", "normalized_disease_key"),
        Index("idx_diagnosis_history_source_file_id", "source_file_id"),
        Index("idx_diagnosis_history_patient_disease_visit", "patient_id", "normalized_disease_key", "visit_date"),
    )

    patient_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_person_identifier: Mapped[str | None] = mapped_column(Text, comment="Raw unified identifier from source row for audit and later identifier-based matching")
    diagnosis_code: Mapped[str | None] = mapped_column(Text)
    diagnosis_name: Mapped[str | None] = mapped_column(Text)
    raw_service_type: Mapped[str | None] = mapped_column(Text)
    normalized_person_identifier: Mapped[str | None] = mapped_column(Text)
    normalized_service_key: Mapped[str | None] = mapped_column(Text)
    normalized_disease_key: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(Text)
    doctor_name: Mapped[str | None] = mapped_column(Text)
    source_import_job_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("import_jobs.id"))
    source_file_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("source_files.id", ondelete="SET NULL"))
    source_file_name: Mapped[str | None] = mapped_column(Text)
    source_row_no: Mapped[int | None] = mapped_column(Integer)
