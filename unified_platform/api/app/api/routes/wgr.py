from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreCompany, CoreUser
from app.models.integration import IntStoreChannel, IntStoreConnection, IntSyncQueue
from app.services.wgr import WGRClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration/wgr", tags=["wgr-integration"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class WGRConnectionCreate(BaseModel):
    api_url: str
    username: str
    password: str
    company_id: int = 1


class WGRConnectionResponse(BaseModel):
    id: int
    api_base_url: str
    active: bool
    last_sync_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_connection_or_404(connection_id: int, db: Session) -> IntStoreConnection:
    conn = db.scalar(
        select(IntStoreConnection).where(
            IntStoreConnection.id == connection_id,
            IntStoreConnection.provider == "wgr",
        )
    )
    if conn is None:
        raise HTTPException(status_code=404, detail="WGR connection not found")
    return conn


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/connections")
def create_connection(
    body: WGRConnectionCreate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict[str, Any]:
    """Register a new WGR API connection."""
    company_id = body.company_id if body.company_id != 0 else 1

    # Validate company exists
    company = db.get(CoreCompany, company_id)
    if not company:
        companies = db.scalars(select(CoreCompany).where(CoreCompany.active.is_(True))).all()
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"company_id={company_id} not found.",
                "available": [{"id": c.id, "name": c.legal_name} for c in companies],
            },
        )

    # Auto-create a WGR system channel for this company if one doesn't exist
    wgr_channel = db.scalar(
        select(IntStoreChannel).where(
            IntStoreChannel.company_id == company_id,
            IntStoreChannel.channel_type == "wgr",
        )
    )
    if not wgr_channel:
        wgr_channel = IntStoreChannel(
            company_id=company_id,
            name="WGR Warehouse System",
            channel_type="wgr",
            base_url=body.api_url,
        )
        db.add(wgr_channel)
        db.flush()

    try:
        conn = IntStoreConnection(
            store_channel_id=wgr_channel.id,
            provider="wgr",
            api_base_url=body.api_url,
            consumer_key=body.username,
            consumer_secret=body.password,
            active=True,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"WGR connection already exists: {exc.orig}") from exc

    return {"id": conn.id, "store_channel_id": wgr_channel.id, "company_id": company_id}


@router.get("/connections", response_model=list[WGRConnectionResponse])
def list_connections(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.read")),
) -> list[IntStoreConnection]:
    """List all WGR connections."""
    return db.scalars(
        select(IntStoreConnection)
        .where(IntStoreConnection.provider == "wgr")
        .order_by(IntStoreConnection.id.desc())
    ).all()


@router.post("/connections/{connection_id}/test")
def test_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.read")),
) -> dict[str, Any]:
    """Test a WGR connection by calling Stock.get and measuring response time."""
    conn = _get_connection_or_404(connection_id, db)
    client = WGRClient(conn.api_base_url, conn.consumer_key, conn.consumer_secret)
    t0 = time.monotonic()
    try:
        articles = asyncio.run(client.get_stock())
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {"ok": True, "article_count": len(articles), "response_ms": elapsed_ms}
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.error("WGR test_connection %d failed: %s", connection_id, exc)
        return {"ok": False, "error": str(exc), "response_ms": elapsed_ms}


@router.post("/connections/{connection_id}/sync-stock-now")
def sync_stock_now(
    connection_id: int,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict[str, Any]:
    """Enqueue an immediate WGR stock poll task."""
    _get_connection_or_404(connection_id, db)
    from app.tasks.wgr import poll_stock  # import here to avoid circular at module load

    task = poll_stock.apply_async()
    return {"queued": True, "task_id": task.id}


@router.get("/connections/{connection_id}/orders")
def get_orders(
    connection_id: int,
    hours_back: int = 24,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.read")),
) -> list[dict]:
    """Fetch the latest orders from WGR (up to 50, from the last N hours)."""
    conn = _get_connection_or_404(connection_id, db)
    client = WGRClient(conn.api_base_url, conn.consumer_key, conn.consumer_secret)
    from_time = datetime.now(tz=UTC) - timedelta(hours=hours_back)
    try:
        orders = asyncio.run(client.get_orders(from_time=from_time))
        return orders[:50]
    except Exception as exc:
        logger.error("WGR get_orders %d failed: %s", connection_id, exc)
        raise HTTPException(status_code=502, detail=f"WGR API error: {exc}") from exc
