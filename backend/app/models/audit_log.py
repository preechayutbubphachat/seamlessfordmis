from sqlalchemy import Index, Text
from app.db.types import JSONType
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_logs_entity_type", "entity_type"),
        Index("idx_audit_logs_entity_id", "entity_id"),
        Index("idx_audit_logs_created_at", "created_at"),
    )

    actor: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    old_value_json: Mapped[dict | None] = mapped_column(JSONType())
    new_value_json: Mapped[dict | None] = mapped_column(JSONType())
    ip_address: Mapped[str | None] = mapped_column(Text)
