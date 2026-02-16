from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.core import CoreAuditEvent
from app.models.integration import IntOutboxEvent


def log_audit_event(
    db: Session,
    *,
    actor_user_id: int | None,
    entity_type: str,
    entity_id: str,
    action: str,
    before: dict | None,
    after: dict | None,
    correlation_id: str | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        CoreAuditEvent(
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_jsonb=before,
            after_jsonb=after,
            correlation_id=correlation_id,
            ip=ip,
        )
    )


def enqueue_outbox_event(
    db: Session,
    *,
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    correlation_id: str | None = None,
) -> None:
    db.add(
        IntOutboxEvent(
            event_name=event_name,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status="pending",
            correlation_id=correlation_id,
            created_at=datetime.now(UTC),
        )
    )
