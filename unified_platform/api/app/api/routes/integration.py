from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.integration import IntOutboxEvent

router = APIRouter(prefix="/integration", tags=["integration"])


@router.get("/sync-status")
def sync_status(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("dashboard.read")),
) -> dict:
    pending = db.scalar(select(func.count(IntOutboxEvent.id)).where(IntOutboxEvent.status == "pending")) or 0
    processed = db.scalar(select(func.count(IntOutboxEvent.id)).where(IntOutboxEvent.status == "processed")) or 0
    failed = db.scalar(select(func.count(IntOutboxEvent.id)).where(IntOutboxEvent.status == "failed")) or 0
    last_error = db.scalar(
        select(IntOutboxEvent.error_message)
        .where(IntOutboxEvent.status == "failed")
        .order_by(IntOutboxEvent.id.desc())
        .limit(1)
    )
    return {"pending": int(pending), "processed": int(processed), "failed": int(failed), "last_error": last_error}
