from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.sales import SalesOrder, SalesOrderLine
from app.services.nshift import NShiftClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nshift", tags=["nshift"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ShipRequest(BaseModel):
    printer_id: str
    packed_by: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/printers")
def list_printers(
    _: CoreUser = Depends(require_permission("sync.read")),
) -> list[dict]:
    """List available nShift Cloud Print printers."""
    client = NShiftClient()
    try:
        return asyncio.run(client.get_printers())
    except Exception as exc:
        logger.error("nShift get_printers failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"nShift API error: {exc}") from exc


@router.post("/ship/{order_id}")
def ship_order(
    order_id: int,
    body: ShipRequest,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict[str, Any]:
    """
    Immediately create a nShift shipment and print a label for the given order.
    This is the endpoint called by the Warehouse Portal when a QR code is scanned.
    """
    order = db.get(SalesOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    order_lines = db.scalars(
        select(SalesOrderLine).where(SalesOrderLine.order_id == order_id)
    ).all()

    client = NShiftClient()
    try:
        result = asyncio.run(
            client.create_shipment_and_print(order, list(order_lines), body.printer_id, body.packed_by)
        )
    except Exception as exc:
        logger.error("nShift ship order %d failed: %s", order_id, exc)
        raise HTTPException(status_code=502, detail=f"nShift API error: {exc}") from exc

    # Update order status
    order.status = "shipped"
    order.shipped_at = datetime.now(tz=UTC)
    db.commit()

    return result


@router.get("/history")
def shipment_history(
    date_from: str | None = None,
    packed_by: str | None = None,
    _: CoreUser = Depends(require_permission("sync.read")),
) -> list[dict]:
    """
    Retrieve shipment/activity history from nShift.
    Optionally filter by packed_by (warehouse worker ID).
    """
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date_from format; use ISO 8601")
    else:
        # default: last 7 days
        dt_from = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    client = NShiftClient()
    try:
        history = asyncio.run(client.get_shipment_history(date_from=dt_from, sender_reference=packed_by))
        return history
    except Exception as exc:
        logger.error("nShift history failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"nShift API error: {exc}") from exc


@router.delete("/shipments/{shipment_id}")
def cancel_shipment(
    shipment_id: str,
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict[str, Any]:
    """Cancel a nShift shipment before EDI transmission."""
    client = NShiftClient()
    try:
        ok = asyncio.run(client.cancel_shipment(shipment_id))
        return {"cancelled": ok, "shipment_id": shipment_id}
    except Exception as exc:
        logger.error("nShift cancel_shipment %s failed: %s", shipment_id, exc)
        raise HTTPException(status_code=502, detail=f"nShift API error: {exc}") from exc
