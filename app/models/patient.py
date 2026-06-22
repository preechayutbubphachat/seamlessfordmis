from datetime import date

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("pid", name="uq_patients_pid"),
        UniqueConstraint("citizen_id", name="uq_patients_citizen_id"),
        UniqueConstraint("hn", name="uq_patients_hn"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pid: Mapped[str | None] = mapped_column(String(50), index=True)
    citizen_id: Mapped[str | None] = mapped_column(String(20), index=True)
    hn: Mapped[str | None] = mapped_column(String(50), index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=False, index=True)
    normalized_name: Mapped[str | None] = mapped_column(String(255), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date, index=True)
    source_import_job_id: Mapped[int | None] = mapped_column(Integer)

    diagnosis_history: Mapped[list["DiagnosisHistory"]] = relationship(back_populates="patient")
