import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ImportJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, default="main_source_sync")
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, native_enum=False),
        nullable=False,
        default=ImportJobStatus.pending,
    )
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_manifest_hash_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    source_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_rows: Mapped[int | None] = mapped_column(Integer)
    imported_rows: Mapped[int | None] = mapped_column(Integer)
    error_rows: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    staging_records: Mapped[list["StagingHistoryRecord"]] = relationship(back_populates="import_job")
    diagnosis_history: Mapped[list["DiagnosisHistory"]] = relationship(back_populates="import_job")
    source_files: Mapped[list["ImportJobSourceFile"]] = relationship(back_populates="import_job", cascade="all, delete-orphan")


class ImportJobSourceFile(TimestampMixin, Base):
    __tablename__ = "import_job_source_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)

    import_job: Mapped["ImportJob"] = relationship(back_populates="source_files")
