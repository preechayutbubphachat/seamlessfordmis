import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class TargetGroupStatus(str, enum.Enum):
    uploaded = "uploaded"
    confirmed = "confirmed"
    matched = "matched"
    failed = "failed"


class MatchMethod(str, enum.Enum):
    pid = "pid"
    citizen_id = "citizen_id"
    hn = "hn"
    name_birth_date = "name_birth_date"
    name_only = "name_only"
    unmatched = "unmatched"


class MatchStatus(str, enum.Enum):
    matched = "matched"
    needs_review = "needs_review"
    unmatched = "unmatched"
    ambiguous = "ambiguous"


class ParseStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"


class ResultStatus(str, enum.Enum):
    pending = "pending"
    generated = "generated"
    history_found = "history_found"
    history_not_found = "history_not_found"
    history_unknown = "history_unknown"


class TargetGroupJob(TimestampMixin, Base):
    __tablename__ = "target_group_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_jobs.id", ondelete="SET NULL"), index=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_file_type: Mapped[str] = mapped_column(String(20), nullable=False, default="excel")
    uploaded_by: Mapped[str | None] = mapped_column(String(100))
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, native_enum=False),
        nullable=False,
        default=ParseStatus.pending,
    )
    match_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, native_enum=False),
        nullable=False,
        default=ParseStatus.pending,
    )
    status: Mapped[TargetGroupStatus] = mapped_column(
        Enum(TargetGroupStatus, native_enum=False),
        nullable=False,
        default=TargetGroupStatus.uploaded,
    )
    total_rows: Mapped[int | None] = mapped_column(Integer)
    valid_rows: Mapped[int | None] = mapped_column(Integer)
    invalid_rows: Mapped[int | None] = mapped_column(Integer)
    review_rows: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    confirmed_at: Mapped[date | None] = mapped_column(Date)
    matched_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class TargetGroupRow(TimestampMixin, Base):
    __tablename__ = "target_group_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    pid: Mapped[str | None] = mapped_column(String(50), index=True)
    citizen_id: Mapped[str | None] = mapped_column(String(20), index=True)
    hn: Mapped[str | None] = mapped_column(String(50), index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, native_enum=False),
        nullable=False,
        default=ParseStatus.pending,
    )
    match_status: Mapped[MatchStatus | None] = mapped_column(Enum(MatchStatus, native_enum=False))
    matched_patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"), index=True)
    confidence_flag: Mapped[str | None] = mapped_column(String(30))
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_errors: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)


class TargetGroupResult(TimestampMixin, Base):
    __tablename__ = "target_group_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    target_group_row_id: Mapped[int] = mapped_column(ForeignKey("target_group_rows.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"), index=True)
    match_method: Mapped[MatchMethod] = mapped_column(Enum(MatchMethod, native_enum=False), nullable=False)
    match_status: Mapped[MatchStatus] = mapped_column(Enum(MatchStatus, native_enum=False), nullable=False)
    confidence_score: Mapped[str | None] = mapped_column(String(20))
    selected_disease_key: Mapped[str | None] = mapped_column(String(100), index=True)
    disease_key: Mapped[str | None] = mapped_column(String(100), index=True)
    disease_code: Mapped[str | None] = mapped_column(String(100))
    disease_name: Mapped[str | None] = mapped_column(String(255))
    has_disease_history: Mapped[bool | None] = mapped_column(Boolean)
    latest_visit_date: Mapped[date | None] = mapped_column(Date)
    visit_count: Mapped[int | None] = mapped_column(Integer)
    days_since_latest_visit: Mapped[int | None] = mapped_column(Integer)
    years_since_latest_visit: Mapped[float | None] = mapped_column(Numeric(10, 2))
    result_status: Mapped[ResultStatus] = mapped_column(
        Enum(ResultStatus, native_enum=False),
        nullable=False,
        default=ResultStatus.pending,
    )
    matched_disease_keys_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    matched_disease_labels_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    matched_service_items_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    query_filters_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    flags_json: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
