from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TargetGroupJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "target_group_jobs"
    __table_args__ = (
        Index("idx_target_group_jobs_parse_status", "parse_status"),
        Index("idx_target_group_jobs_match_status", "match_status"),
        Index("idx_target_group_jobs_source_set_hash", "source_set_hash"),
    )

    import_job_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("import_jobs.id", ondelete="SET NULL"))
    group_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="excel, csv, pdf")
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA-256 ของไฟล์อ้างอิงหลัก")
    source_set_hash: Mapped[str | None] = mapped_column(String(64), comment="SHA-256 ของชุดไฟล์กลุ่มเป้าหมายทั้งหมด")
    source_file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uploaded_by: Mapped[str | None] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    match_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_cid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_cid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
