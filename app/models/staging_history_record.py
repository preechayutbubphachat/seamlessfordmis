from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class StagingHistoryRecord(TimestampMixin, Base):
    __tablename__ = "staging_history_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_sheet_name: Mapped[str] = mapped_column(String(100), nullable=False, default="Individual")
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    pid: Mapped[str | None] = mapped_column(String(50), index=True)
    citizen_id: Mapped[str | None] = mapped_column(String(20), index=True)
    hn: Mapped[str | None] = mapped_column(String(50), index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    visit_date: Mapped[date | None] = mapped_column(Date)
    diagnosis_code: Mapped[str | None] = mapped_column(String(50), index=True)
    disease_name_raw: Mapped[str | None] = mapped_column(String(255))
    normalized_disease_key: Mapped[str | None] = mapped_column(String(100), index=True)
    validation_errors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    import_job: Mapped["ImportJob"] = relationship(back_populates="staging_records")
