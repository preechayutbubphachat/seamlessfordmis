from uuid import UUID

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TargetGroupJobFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "target_group_job_files"
    __table_args__ = (
        Index("idx_target_group_job_files_group_job_id", "group_job_id"),
        Index("idx_target_group_job_files_sha256", "sha256"),
        Index("idx_target_group_job_files_file_type", "file_type"),
    )

    group_job_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("target_group_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="excel, csv, pdf_text, pdf_scanned")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    source_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    parse_error_summary: Mapped[str | None] = mapped_column(Text)
