from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from app.db.types import GUID, JSONType
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class TargetGroupResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "target_group_results"
    __table_args__ = (
        Index("idx_target_group_results_group_job_id", "group_job_id"),
        Index("idx_target_group_results_target_row_id", "target_row_id"),
        Index("idx_target_group_results_normalized_cid", "normalized_cid"),
        Index("idx_target_group_results_selected_service_hash", "selected_service_hash"),
        # Phase D: allow DB-level filtering by review status, link method, person key
        Index("idx_target_group_results_group_review", "group_job_id", "review_required"),
        Index("idx_target_group_results_group_link_status", "group_job_id", "person_link_status"),
        Index("idx_target_group_results_canonical_key", "group_job_id", "canonical_person_key"),
    )

    group_job_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False)
    target_row_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("target_group_rows.id", ondelete="CASCADE"))
    patient_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("patients.id", ondelete="SET NULL"))

    # Legacy-compatible fields remain mapped so older export/report paths keep working
    # while Phase 5 stores richer multi-select context alongside them.
    disease_key: Mapped[str | None] = mapped_column(Text)
    disease_code: Mapped[str | None] = mapped_column(Text)
    disease_name: Mapped[str | None] = mapped_column(Text)
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    normalized_cid: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(20))

    has_selected_service: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    matching_record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_service_keys: Mapped[list[str] | None] = mapped_column(JSONType())
    selected_service_keys: Mapped[list[str]] = mapped_column(JSONType(), nullable=False)
    selected_service_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    last_visit_date: Mapped[date | None] = mapped_column(Date)
    days_since_last_visit: Mapped[int | None] = mapped_column(Integer)
    years_since_last_visit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    result_status: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")
    warning_message: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())

    # Phase D: person-level consolidation fields.
    # canonical_person_key is the grouping key from _person_group_key().
    # Storing it makes get_results() context lookups stable across calls.
    canonical_person_key: Mapped[str | None] = mapped_column(Text)
    # person_link_status: citizen_id_exact | name_birthdate_exact |
    #   name_birthdate_address_secondary | review_required | insufficient_identity_data
    person_link_status: Mapped[str | None] = mapped_column(String(40))
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duplicate_reason: Mapped[str | None] = mapped_column(Text)
