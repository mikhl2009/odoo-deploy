from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.inventory import (
    InvCountLine,
    InvCountSession,
    InvReplenishmentRule,
    InvStockAlert,
    InvStockBalance,
    InvStockMovement,
    InvValuationLayer,
)
from app.schemas.inventory import (
    CountLineCreate,
    CountSessionCreate,
    ReplenishmentRuleCreate,
    StockBalanceResponse,
    StockMovementCreate,
    StockMovementResponse,
)
from app.services.audit import enqueue_outbox_event, log_audit_event
from app.ws.manager import ws_manager

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _upsert_stock_balance(
    db: Session,
    *,
    company_id: int,
    location_id: int,
    variant_id: int,
    lot_id: int | None,
    container_id: int | None,
    qty_delta: Decimal,
) -> InvStockBalance:
    balance = db.scalar(
        select(InvStockBalance).where(
            InvStockBalance.company_id == company_id,
            InvStockBalance.location_id == location_id,
            InvStockBalance.variant_id == variant_id,
            InvStockBalance.lot_id == lot_id,
            InvStockBalance.container_id == container_id,
        )
    )
    if not balance:
        balance = InvStockBalance(
            company_id=company_id,
            location_id=location_id,
            variant_id=variant_id,
            lot_id=lot_id,
            container_id=container_id,
            on_hand_qty=0,
            reserved_qty=0,
            available_qty=0,
        )
        db.add(balance)
        db.flush()

    balance.on_hand_qty = (Decimal(balance.on_hand_qty) + qty_delta)
    balance.available_qty = Decimal(balance.on_hand_qty) - Decimal(balance.reserved_qty)
    return balance


@router.get("/stock", response_model=list[StockBalanceResponse])
def stock(
    location_id: int | None = None,
    variant_id: int | None = None,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("inventory.read")),
) -> list[InvStockBalance]:
    stmt = select(InvStockBalance)
    if location_id:
        stmt = stmt.where(InvStockBalance.location_id == location_id)
    if variant_id:
        stmt = stmt.where(InvStockBalance.variant_id == variant_id)
    return db.scalars(stmt.order_by(InvStockBalance.id.desc()).limit(1000)).all()


@router.get("/movements", response_model=list[StockMovementResponse])
def movements(
    location_id: int | None = None,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("inventory.read")),
) -> list[InvStockMovement]:
    stmt = select(InvStockMovement)
    if location_id:
        stmt = stmt.where(
            (InvStockMovement.source_location_id == location_id)
            | (InvStockMovement.dest_location_id == location_id)
        )
    return db.scalars(stmt.order_by(InvStockMovement.id.desc()).limit(1000)).all()


@router.post("/transfers", response_model=StockMovementResponse)
async def transfer(
    payload: StockMovementCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("inventory.write")),
) -> InvStockMovement:
    if payload.source_location_id is None or payload.dest_location_id is None:
        raise HTTPException(status_code=400, detail="source_location_id and dest_location_id required")

    movement = InvStockMovement(
        **payload.model_dump(),
        movement_type="transfer",
        moved_by=user.id,
        moved_at=datetime.now(UTC),
    )
    db.add(movement)
    db.flush()
    _upsert_stock_balance(
        db,
        company_id=payload.company_id,
        location_id=payload.source_location_id,
        variant_id=payload.variant_id,
        lot_id=payload.lot_id,
        container_id=payload.container_id,
        qty_delta=Decimal("-1") * payload.qty,
    )
    _upsert_stock_balance(
        db,
        company_id=payload.company_id,
        location_id=payload.dest_location_id,
        variant_id=payload.variant_id,
        lot_id=payload.lot_id,
        container_id=payload.container_id,
        qty_delta=payload.qty,
    )
    enqueue_outbox_event(
        db,
        event_name="stock.changed",
        aggregate_type="stock_movement",
        aggregate_id=str(movement.id),
        payload={"movement_id": movement.id, "type": movement.movement_type},
    )
    db.commit()
    db.refresh(movement)
    await ws_manager.broadcast(f"inventory:{payload.source_location_id}", {"event": "stock_changed", "movement_id": movement.id})
    await ws_manager.broadcast(f"inventory:{payload.dest_location_id}", {"event": "stock_changed", "movement_id": movement.id})
    return movement


@router.post("/adjustments", response_model=StockMovementResponse)
async def adjustment(
    payload: StockMovementCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("inventory.write")),
) -> InvStockMovement:
    target_location = payload.dest_location_id or payload.source_location_id
    if target_location is None:
        raise HTTPException(status_code=400, detail="source_location_id or dest_location_id required")

    movement = InvStockMovement(
        **payload.model_dump(),
        movement_type="adjustment",
        moved_by=user.id,
        moved_at=datetime.now(UTC),
    )
    db.add(movement)
    db.flush()
    _upsert_stock_balance(
        db,
        company_id=payload.company_id,
        location_id=target_location,
        variant_id=payload.variant_id,
        lot_id=payload.lot_id,
        container_id=payload.container_id,
        qty_delta=payload.qty,
    )
    db.add(
        InvValuationLayer(
            movement_id=movement.id,
            variant_id=payload.variant_id,
            location_id=target_location,
            method="wac",
            qty_in=payload.qty if payload.qty > 0 else 0,
            qty_out=abs(payload.qty) if payload.qty < 0 else 0,
            unit_cost=0,
            total_cost=0,
            remaining_qty=payload.qty if payload.qty > 0 else 0,
            remaining_cost=0,
        )
    )
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="inv_stock_movement",
        entity_id=str(movement.id),
        action="adjustment",
        before=None,
        after=payload.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(movement)
    await ws_manager.broadcast(f"inventory:{target_location}", {"event": "stock_changed", "movement_id": movement.id})
    return movement


@router.get("/valuation")
def valuation(
    method: str = Query(default="fifo", pattern="^(fifo|wac)$"),
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("inventory.read")),
) -> dict:
    total = db.scalar(select(func.coalesce(func.sum(InvValuationLayer.remaining_cost), 0)).where(InvValuationLayer.method == method))
    return {"method": method, "stock_value": float(total or 0)}


@router.get("/alerts")
def alerts(
    status: str = "open",
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("inventory.read")),
) -> list[dict]:
    rows = db.scalars(select(InvStockAlert).where(InvStockAlert.status == status).order_by(InvStockAlert.id.desc())).all()
    return [
        {
            "id": row.id,
            "location_id": row.location_id,
            "variant_id": row.variant_id,
            "alert_type": row.alert_type,
            "threshold_value": float(row.threshold_value),
            "current_value": float(row.current_value),
            "status": row.status,
        }
        for row in rows
    ]


@router.post("/replenishment/rules")
def create_replenishment_rule(
    payload: ReplenishmentRuleCreate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("inventory.write")),
) -> dict:
    existing = db.scalar(
        select(InvReplenishmentRule).where(
            InvReplenishmentRule.company_id == payload.company_id,
            InvReplenishmentRule.location_id == payload.location_id,
            InvReplenishmentRule.variant_id == payload.variant_id,
        )
    )
    if existing:
        existing.min_qty = payload.min_qty
        existing.max_qty = payload.max_qty
        existing.reorder_qty = payload.reorder_qty
        existing.preferred_supplier_id = payload.preferred_supplier_id
        existing.lead_time_days_override = payload.lead_time_days_override
        db.commit()
        return {"id": existing.id, "updated": True}

    rule = InvReplenishmentRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    return {"id": rule.id, "updated": False}


@router.post("/count-sessions")
def create_count_session(
    payload: CountSessionCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("inventory.write")),
) -> dict:
    session = InvCountSession(
        company_id=payload.company_id,
        location_id=payload.location_id,
        status="in_progress",
        started_by=user.id,
        started_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()
    return {"id": session.id, "status": session.status}


@router.post("/count-sessions/{session_id}/lines")
def add_count_lines(
    session_id: int,
    payload: list[CountLineCreate],
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("inventory.write")),
) -> dict:
    session = db.get(InvCountSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Count session not found")
    db.execute(delete(InvCountLine).where(InvCountLine.session_id == session_id))
    for line in payload:
        diff = line.counted_qty - line.expected_qty
        db.add(
            InvCountLine(
                session_id=session_id,
                variant_id=line.variant_id,
                lot_id=line.lot_id,
                expected_qty=line.expected_qty,
                counted_qty=line.counted_qty,
                diff_qty=diff,
                reason_code=line.reason_code,
            )
        )
    db.commit()
    return {"session_id": session_id, "lines_saved": len(payload)}


@router.post("/count-sessions/{session_id}/close")
def close_count_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("inventory.write")),
) -> dict:
    session = db.get(InvCountSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Count session not found")

    lines = db.scalars(select(InvCountLine).where(InvCountLine.session_id == session_id)).all()
    for line in lines:
        balance = db.scalar(
            select(InvStockBalance).where(
                InvStockBalance.company_id == session.company_id,
                InvStockBalance.location_id == session.location_id,
                InvStockBalance.variant_id == line.variant_id,
                InvStockBalance.lot_id == line.lot_id,
            )
        )
        if balance:
            balance.on_hand_qty = line.counted_qty
            balance.available_qty = Decimal(balance.on_hand_qty) - Decimal(balance.reserved_qty)

    session.status = "closed"
    session.closed_by = user.id
    session.closed_at = datetime.now(UTC)
    db.commit()
    return {"status": session.status}
