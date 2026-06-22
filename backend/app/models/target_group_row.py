from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from app.db.types import GUID, JSONType
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TargetGroupRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "target_group_rows"
    __table_args__ = (
        Index("idx_target_group_rows_group_job_id", "group_job_id"),
        Index("idx_target_group_rows_match_status", "match_status"),
        Index("idx_target_group_rows_matched_patient_id", "matched_patient_id"),
        Index("idx_target_group_rows_source_file_id", "source_file_id"),
        Index("idx_target_group_rows_normalized_cid", "normalized_cid"),
        Index("idx_target_group_rows_normalized_full_name", "normalized_full_name"),
        Index("idx_target_group_rows_duplicate_status", "duplicate_status"),
    )

    group_job_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False)
    source_file_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("target_group_job_files.id", ondelete="SET NULL"))
    source_file_name: Mapped[str | None] = mapped_column(Text)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_row_no: Mapped[int | None] = mapped_column(Integer)

    raw_cid: Mapped[str | None] = mapped_column(Text, comment="Raw CID from target group source file")
    raw_pid: Mapped[str | None] = mapped_column(Text)
    raw_citizen_id: Mapped[str | None] = mapped_column(Text)
    raw_hn: Mapped[str | None] = mapped_column(Text)
    raw_full_name: Mapped[str | None] = mapped_column(Text)
    raw_birth_date: Mapped[str | None] = mapped_column(Text)
    raw_age: Mapped[str | None] = mapped_column(Text)
    raw_sex: Mapped[str | None] = mapped_column(Text)
    raw_target_history_labels: Mapped[str | None] = mapped_column(Text)
    raw_target_history_note: Mapped[str | None] = mapped_column(Text)
    raw_target_history_last_visit_date: Mapped[str | None] = mapped_column(Text)

    normalized_cid: Mapped[str | None] = mapped_column(Text)
    normalized_pid: Mapped[str | None] = mapped_column(Text)
    normalized_citizen_id: Mapped[str | None] = mapped_column(Text)
    normalized_hn: Mapped[str | None] = mapped_column(Text)
    normalized_full_name: Mapped[str | None] = mapped_column(Text)
    normalized_birth_date: Mapped[date | None] = mapped_column(Date)
    normalized_age: Mapped[int | None] = mapped_column(Integer)
    normalized_sex: Mapped[str | None] = mapped_column(String(20))
    normalized_target_history_service_keys: Mapped[list[str] | None] = mapped_column(JSONType())
    normalized_target_history_last_visit_date: Mapped[date | None] = mapped_column(Date)

    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    cid_validation_status: Mapped[str | None] = mapped_column(String(30))
    duplicate_status: Mapped[str | None] = mapped_column(String(30), comment="unique_in_job, duplicate_in_job")
    match_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    match_method: Mapped[str | None] = mapped_column(String(40), comment="identifier_exact, name_exact_secondary, not_found, needs_review")
    matched_patient_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("patients.id", ondelete="SET NULL"))
    matched_identifier_basis: Mapped[str | None] = mapped_column(Text)
    matched_name_basis: Mapped[str | None] = mapped_column(Text)
    confidence_flag: Mapped[str | None] = mapped_column(String(30), comment="high, medium, low")
    error_message: Mapped[str | None] = mapped_column(Text)
    warning_message: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict | None] = mapped_column(JSONType(), comment="ค่าดิบจากไฟล์กลุ่มเป้าหมายสำหรับ trace และ review")
