from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreAuditEvent, CoreUser

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def list_audit_events(
    entity_type: str | None = None,
    entity_id: str | None = None,
    correlation_id: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("rbac.read")),
) -> list[dict]:
    stmt = select(CoreAuditEvent)
    if entity_type:
        stmt = stmt.where(CoreAuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(CoreAuditEvent.entity_id == entity_id)
    if correlation_id:
        stmt = stmt.where(CoreAuditEvent.correlation_id == correlation_id)
    rows = db.scalars(stmt.order_by(CoreAuditEvent.id.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "actor_user_id": row.actor_user_id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "action": row.action,
            "correlation_id": row.correlation_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "before": row.before_jsonb,
            "after": row.after_jsonb,
        }
        for row in rows
    ]
