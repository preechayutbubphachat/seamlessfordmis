from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, Numeric, Text
from app.db.types import GUID, JSONType
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TargetGroupSheet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "target_group_sheets"
    __table_args__ = (
        Index("idx_target_group_sheets_group_job_id", "group_job_id"),
        Index("idx_target_group_sheets_source_file_id", "source_file_id"),
        Index("idx_target_group_sheets_sheet_type", "sheet_type"),
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
    sheet_name: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sheet_type: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_names_json: Mapped[list[str] | None] = mapped_column(JSONType())
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(4, 2))
    notes: Mapped[str | None] = mapped_column(Text)
