from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ImportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (
        Index("idx_import_jobs_source_type", "source_type"),
        Index("idx_import_jobs_status", "status"),
        Index("idx_import_jobs_hash", "source_file_hash"),
        Index("idx_import_jobs_source_set_hash", "source_set_hash"),
    )

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_file_path: Mapped[str | None] = mapped_column(Text)
    source_file_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="SHA-256 ของไฟล์อ้างอิงหลัก")
    source_set_hash: Mapped[str | None] = mapped_column(String(64), comment="SHA-256 ของชุดไฟล์ต้นทางทั้งหมด")
    source_file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_file_size: Mapped[int | None] = mapped_column(BigInteger)
    source_file_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merged_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_identifier_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_by: Mapped[str | None] = mapped_column(Text)
    error_summary: Mapped[str | None] = mapped_column(Text)
