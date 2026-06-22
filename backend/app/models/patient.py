from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, String, Text, text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Patient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        Index("uq_patients_pid", "pid", unique=True, postgresql_where=text("pid IS NOT NULL")),
        Index("uq_patients_citizen_id", "citizen_id", unique=True, postgresql_where=text("citizen_id IS NOT NULL")),
        Index("idx_patients_hn", "hn"),
        Index("idx_patients_full_name", "full_name"),
        Index("idx_patients_birth_date", "birth_date"),
    )

    pid: Mapped[str | None] = mapped_column(Text)
    citizen_id: Mapped[str | None] = mapped_column(Text, comment="เลขบัตรประชาชน ใช้ match รองจาก PID")
    hn: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(20))
    source_import_job_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("import_jobs.id"))
