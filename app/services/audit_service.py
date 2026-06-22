from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.schemas.common import AuditLogCreate


class AuditService:
    @staticmethod
    def log(db: Session, payload: AuditLogCreate) -> AuditLog:
        entry = AuditLog(**payload.model_dump())
        db.add(entry)
        db.flush()
        return entry
