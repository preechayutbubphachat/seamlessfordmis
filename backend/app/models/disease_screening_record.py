from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DiseaseScreeningRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "disease_screening_records"
    __table_args__ = (
        Index("idx_disease_screening_records_import_job_id", "source_import_job_id"),
        Index("idx_disease_screening_records_source_file_id", "source_file_id"),
        Index("idx_disease_screening_records_identifier", "normalized_person_identifier"),
        Index("idx_disease_screening_records_normalized_full_name", "normalized_full_name"),
        Index("idx_disease_screening_records_service_key", "normalized_service_key"),
        Index("idx_disease_screening_records_visit_date", "visit_date"),
        Index(
            "uq_disease_screening_records_source_row",
            "source_import_job_id",
            "source_file_id",
            "source_row_no",
            unique=True,
        ),
    )

    source_import_job_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_file_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("source_files.id", ondelete="SET NULL"),
    )
    source_file_name: Mapped[str | None] = mapped_column(Text)
    source_row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    raw_person_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_person_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    normalized_full_name: Mapped[str | None] = mapped_column(Text)

    raw_service_type: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_service_key: Mapped[str] = mapped_column(Text, nullable=False)

    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    hcode: Mapped[str | None] = mapped_column(Text)
    transaction_id: Mapped[str | None] = mapped_column(Text)
    rep_no: Mapped[str | None] = mapped_column(Text)
