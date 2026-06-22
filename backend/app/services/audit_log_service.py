from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.schemas.common import AuditLogCreate


class AuditLogService:
    @staticmethod
    def create(db: Session, payload: AuditLogCreate) -> AuditLog:
        entry = AuditLog(**payload.model_dump())
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def create_event(
        db: Session,
        *,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: str = "system",
        status: str,
        context: dict | None = None,
        error_summary: str | None = None,
    ) -> AuditLog:
        payload = {
            "status": status,
            **(context or {}),
        }
        if error_summary:
            payload["error_summary"] = error_summary
        return AuditLogService.create(
            db,
            AuditLogCreate(
                actor=actor,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                new_value_json=payload,
            ),
        )
