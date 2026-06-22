from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from app.db.types import GUID, JSONType
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPrimaryKeyMixin


class TargetGroupResultSummary(UUIDPrimaryKeyMixin, Base):
    """Cached result summary written at generate() time.

    Stores a snapshot of the aggregate counts so that get_result_summary()
    can serve from this table with a single primary-key lookup instead of
    re-aggregating all TargetGroupResult rows on every request.

    One row per (group_job_id, selected_service_hash) pair.  The hash allows
    the summary to be invalidated and re-generated when the selected services
    change without losing history for other service selections.
    """

    __tablename__ = "target_group_result_summaries"
    __table_args__ = (
        Index(
            "idx_tgrs_group_service_hash",
            "group_job_id",
            "selected_service_hash",
            unique=True,
        ),
    )

    group_job_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("target_group_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    selected_service_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_service_keys: Mapped[list[str]] = mapped_column(JSONType(), nullable=False)
    overdue_threshold_years: Mapped[int | None] = mapped_column(Integer)

    # Headcount aggregates
    total_target_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_identifier_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_identifier_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    non_thai_nationality_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    insufficient_identity_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outside_target_scope_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_required_identity_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # History coverage
    people_with_selected_history: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    people_without_selected_history: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    never_checked_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_but_overdue_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_and_within_threshold_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Coverage formula output
    coverage_percent: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)

    # Source file manifest hash at generation time — used for stale detection
    source_set_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Normalization/classification logic version at generation time. Nullable so
    # pre-existing cached rows (generated before this column) read as NULL and are
    # treated as stale → the UI prompts the user to regenerate. See
    # RESULT_NORMALIZATION_VERSION in result_generation_service.
    normalization_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
