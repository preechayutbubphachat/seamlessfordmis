from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class DiagnosisHistory(TimestampMixin, Base):
    __tablename__ = "diagnosis_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    visit_date: Mapped[date | None] = mapped_column(Date, index=True)
    diagnosis_code: Mapped[str | None] = mapped_column(String(50), index=True)
    disease_name_raw: Mapped[str | None] = mapped_column(String(255))
    normalized_disease_key: Mapped[str | None] = mapped_column(String(100), index=True)
    encounter_type: Mapped[str | None] = mapped_column(String(100))
    provider_name: Mapped[str | None] = mapped_column(String(255))
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sheet_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Individual")
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="diagnosis_history")
    import_job: Mapped["ImportJob"] = relationship(back_populates="diagnosis_history")
