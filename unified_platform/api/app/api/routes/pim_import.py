"""
PIM import endpoints.

POST /api/v1/pim/import-from-woo/{connection_id}
    Runs WooCommerce to PIM import in a FastAPI background thread.
    Returns {task_id, status:"queued"} immediately.

GET /api/v1/pim/import-status/{task_id}
    Poll task state and result (in-memory; resets on restart).

Usage:
  POST /api/v1/pim/import-from-woo/1?location_id=1&seed_stock=false
  GET  /api/v1/pim/import-status/<task_id>
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.db.session import SessionLocal
from app.models.core import CoreUser
from app.models.integration import IntStoreConnection
from app.services.pim_import import run_woo_import

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pim", tags=["pim-import"])

# In-memory task store - lost on restart, sufficient for demo
_tasks: dict[str, dict[str, Any]] = {}


def _run_import(task_id: str, connection_id: int, location_id: int, seed_stock: bool) -> None:
    """Import WooCommerce products into PIM in a background thread."""
    _tasks[task_id] = {"status": "running"}
    db = SessionLocal()
    try:
        result = run_woo_import(
            db,
            connection_id=connection_id,
            location_id=location_id,
            seed_stock=seed_stock,
            create_location_if_missing=True,
        )
        _tasks[task_id] = {"status": "success", "result": result}
        logger.info(
            "WooImport task=%s conn=%d imported=%d updated=%d skipped=%d names=%d brands=%d prices=%d",
            task_id,
            connection_id,
            result.get("imported", 0),
            result.get("updated", 0),
            result.get("skipped", 0),
            result.get("names_synced", 0),
            result.get("brands_synced", 0),
            result.get("prices_synced", 0),
        )

    except Exception as exc:
        logger.exception("WooImport task=%s failed: %s", task_id, exc)
        _tasks[task_id] = {"status": "failure", "error": str(exc)}
    finally:
        db.close()


@router.post(
    "/import-from-woo/{connection_id}",
    summary="Queue WooCommerce to PIM import",
    status_code=202,
)
def import_from_woo(
    connection_id: int,
    background_tasks: BackgroundTasks,
    location_id: int = Query(
        default=1,
        description="core_location.id to seed InvStockBalance rows (must exist)",
    ),
    seed_stock: bool = Query(
        default=True,
        description="Upsert InvStockBalance.on_hand_qty from Woo stock_quantity",
    ),
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    """
    Validates the connection and queues the import as a FastAPI background thread.
    Returns {task_id, status:"queued"}. Poll GET /pim/import-status/{task_id} for result.
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

    task_id = str(uuid.uuid4())
    _tasks[task_id] = {"status": "queued"}
    background_tasks.add_task(_run_import, task_id, connection_id, location_id, seed_stock)
    logger.info("Queued WooImport task %s for connection %d", task_id, connection_id)
    return {"task_id": task_id, "status": "queued", "connection_id": connection_id}


@router.get("/import-status/{task_id}", summary="Poll WooCommerce import task status")
def import_status(
    task_id: str,
    _: CoreUser = Depends(require_permission("sync.read")),
) -> dict:
    """
    Returns task state and result for a queued import job.
    States: queued | running | success | failure | unknown
    NOTE: State is in-memory and resets when the API container restarts.
    """
    state = _tasks.get(task_id)
    if state is None:
        return {"task_id": task_id, "status": "unknown"}
    return {"task_id": task_id, **state}


@router.post("/dedup-stock", summary="Admin: remove duplicate InvStockBalance rows, keep lowest id per key")
def dedup_stock(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    """
    Deletes duplicate inv_stock_balance rows, keeping the one with the lowest id
    per (company_id, location_id, variant_id, lot_id, container_id) group.
    Safe to run multiple times.
    """
    from sqlalchemy import text
    result = db.execute(text("""
        DELETE FROM inv_stock_balance
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM inv_stock_balance
            GROUP BY company_id, location_id, variant_id, lot_id, container_id
        )
    """))
    db.commit()
    return {"deleted": result.rowcount, "message": "Duplicate stock balance rows removed"}
