from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, String, Text
from app.db.types import GUID, JSONType
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class StagingHistoryRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staging_history_records"
    __table_args__ = (
        Index("idx_staging_history_import_job_id", "import_job_id"),
        Index("idx_staging_history_validation_status", "validation_status"),
        Index("idx_staging_history_source_file_id", "source_file_id"),
    )

    import_job_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False)
    source_file_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("source_files.id", ondelete="SET NULL"))
    source_file_name: Mapped[str | None] = mapped_column(Text)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_row_no: Mapped[int | None] = mapped_column(Integer)

    raw_person_identifier: Mapped[str | None] = mapped_column(Text, comment="Raw unified identifier from source column VCTID,NAPNumber,PID")
    raw_pid: Mapped[str | None] = mapped_column(Text)
    raw_citizen_id: Mapped[str | None] = mapped_column(Text)
    raw_hn: Mapped[str | None] = mapped_column(Text)
    raw_full_name: Mapped[str | None] = mapped_column(Text)
    raw_birth_date: Mapped[str | None] = mapped_column(Text)
    raw_visit_date: Mapped[str | None] = mapped_column(Text)
    raw_service_type: Mapped[str | None] = mapped_column(Text)
    raw_hcode: Mapped[str | None] = mapped_column(Text)
    raw_transaction_id: Mapped[str | None] = mapped_column(Text)
    raw_rep_no: Mapped[str | None] = mapped_column(Text)
    raw_diagnosis_code: Mapped[str | None] = mapped_column(Text)
    raw_diagnosis_name: Mapped[str | None] = mapped_column(Text)
    raw_department: Mapped[str | None] = mapped_column(Text)
    raw_doctor_name: Mapped[str | None] = mapped_column(Text)

    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    identifier_validation_status: Mapped[str | None] = mapped_column(String(30))
    date_validation_status: Mapped[str | None] = mapped_column(String(30))
    service_validation_status: Mapped[str | None] = mapped_column(String(30))
    confidence_flag: Mapped[str | None] = mapped_column(String(30), comment="high, medium, low")
    error_message: Mapped[str | None] = mapped_column(Text)
    warning_message: Mapped[str | None] = mapped_column(Text)

    normalized_person_identifier: Mapped[str | None] = mapped_column(Text)
    normalized_pid: Mapped[str | None] = mapped_column(Text)
    normalized_citizen_id: Mapped[str | None] = mapped_column(Text)
    normalized_hn: Mapped[str | None] = mapped_column(Text)
    normalized_full_name: Mapped[str | None] = mapped_column(Text)
    normalized_birth_date: Mapped[date | None] = mapped_column(Date)
    normalized_visit_date: Mapped[date | None] = mapped_column(Date)
    normalized_service_key: Mapped[str | None] = mapped_column(Text)
    normalized_diagnosis_code: Mapped[str | None] = mapped_column(Text)
    normalized_diagnosis_name: Mapped[str | None] = mapped_column(Text)
    normalized_disease_key: Mapped[str | None] = mapped_column(Text)

    raw_json: Mapped[dict | None] = mapped_column(JSONType(), comment="เก็บค่าดิบจากไฟล์เพื่อ audit และ re-parse ในอนาคต")
