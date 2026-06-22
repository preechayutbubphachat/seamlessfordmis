from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from app.db.types import GUID, JSONType
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TargetGroupHistoryRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "target_group_history_rows"
    __table_args__ = (
        Index("idx_target_group_history_rows_group_job_id", "group_job_id"),
        Index("idx_target_group_history_rows_source_file_id", "source_file_id"),
        Index("idx_target_group_history_rows_source_sheet_id", "source_sheet_id"),
        Index("idx_target_group_history_rows_source_sheet_name", "source_sheet_name"),
        Index("idx_target_group_history_rows_normalized_cid", "normalized_cid"),
        Index("idx_target_group_history_rows_normalized_full_name", "normalized_full_name"),
        Index("idx_target_group_history_rows_service_key", "normalized_service_key"),
        Index("idx_target_group_history_rows_visit_date", "normalized_visit_date"),
    )

    group_job_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("target_group_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_file_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("target_group_job_files.id", ondelete="SET NULL"),
    )
    source_sheet_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("target_group_sheets.id", ondelete="SET NULL"),
    )
    source_file_name: Mapped[str | None] = mapped_column(Text)
    source_sheet_name: Mapped[str | None] = mapped_column(Text)
    source_row_no: Mapped[int | None] = mapped_column(Integer)

    raw_cid: Mapped[str | None] = mapped_column(Text)
    normalized_cid: Mapped[str | None] = mapped_column(Text)
    raw_full_name: Mapped[str | None] = mapped_column(Text)
    normalized_full_name: Mapped[str | None] = mapped_column(Text)
    raw_birth_date: Mapped[str | None] = mapped_column(Text)
    normalized_birth_date: Mapped[date | None] = mapped_column(Date)
    raw_address: Mapped[str | None] = mapped_column(Text)
    normalized_address: Mapped[str | None] = mapped_column(Text)
    raw_service_label: Mapped[str | None] = mapped_column(Text)
    raw_service_type: Mapped[str | None] = mapped_column(Text)
    normalized_service_key: Mapped[str | None] = mapped_column(Text)
    raw_visit_date: Mapped[str | None] = mapped_column(Text)
    normalized_visit_date: Mapped[date | None] = mapped_column(Date)
    raw_icd10: Mapped[str | None] = mapped_column(Text)
    raw_result: Mapped[str | None] = mapped_column(Text)
    raw_hpv: Mapped[str | None] = mapped_column(Text)
    raw_hospital: Mapped[str | None] = mapped_column(Text)
    raw_doctor: Mapped[str | None] = mapped_column(Text)
    raw_note: Mapped[str | None] = mapped_column(Text)

    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    identifier_validation_status: Mapped[str | None] = mapped_column(String(30))
    date_validation_status: Mapped[str | None] = mapped_column(String(30))
    service_validation_status: Mapped[str | None] = mapped_column(String(30))
    warning_message: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSONType())
