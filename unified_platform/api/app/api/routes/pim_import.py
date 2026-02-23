"""
PIM import endpoints.

POST /api/v1/pim/import-from-woo/{connection_id}
    Queues a Celery background task that imports products from WooCommerce into PIM.
    Returns {task_id, status:"queued"} immediately.

GET /api/v1/pim/import-status/{task_id}
    Poll task state and result.

Usage:
  POST /api/v1/pim/import-from-woo/1?location_id=1&seed_stock=true
  GET  /api/v1/pim/import-status/<task_id>
"""
from __future__ import annotations

import logging

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.integration import IntStoreConnection
from app.worker import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pim", tags=["pim-import"])


@router.post("/import-from-woo/{connection_id}", summary="Queue WooCommerce → PIM import", status_code=202)
def import_from_woo(
    connection_id: int,
    location_id: int = Query(
        default=1,
        description="core_location.id to seed InvStockBalance rows (must already exist in DB)",
    ),
    seed_stock: bool = Query(
        default=True,
        description="Upsert InvStockBalance.on_hand_qty from Woo stock_quantity",
    ),
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    """
    Validates the connection exists and has credentials, then immediately queues
    a Celery background task that paginates WooCommerce and upserts PIM records.
    Returns {task_id, status:"queued"} — poll GET /pim/import-status/{task_id} for result.
    """
    conn = db.get(IntStoreConnection, connection_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"Connection {connection_id} not found")

    if not conn.consumer_key or not conn.consumer_secret:
        raise HTTPException(
            status_code=422,
            detail="Connection has no consumer_key/consumer_secret. "
                   "PATCH /integration/woo/connections/{id} to add credentials.",
        )

    from app.tasks.pim import import_from_woo as _task  # noqa: PLC0415
    job = _task.delay(connection_id, location_id, seed_stock)
    logger.info("Queued WooImport task %s for connection %d", job.id, connection_id)
    return {"task_id": job.id, "status": "queued", "connection_id": connection_id}


@router.get("/import-status/{task_id}", summary="Poll WooCommerce import task status")
def import_status(
    task_id: str,
    _: CoreUser = Depends(require_permission("sync.read")),
) -> dict:
    """
    Returns task state and result (or error) for a previously queued import job.
    States: PENDING | STARTED | SUCCESS | FAILURE | REVOKED
    """
    result = AsyncResult(task_id, app=celery_app)
    state = result.state
    if state == "SUCCESS":
        return {"task_id": task_id, "status": "success", "result": result.result}
    if state == "FAILURE":
        return {
            "task_id": task_id,
            "status": "failure",
            "error": str(result.result),
        }
    return {"task_id": task_id, "status": state.lower()}
