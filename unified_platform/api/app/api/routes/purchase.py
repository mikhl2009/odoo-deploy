from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.procurement import ProcPurchaseOrder, ProcPurchaseOrderLine
from app.schemas.supply import PurchaseOrderCreate, PurchaseOrderResponse
from app.services.audit import enqueue_outbox_event, log_audit_event

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])


@router.get("", response_model=list[PurchaseOrderResponse])
def list_purchase_orders(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("purchase.read")),
) -> list[ProcPurchaseOrder]:
    return db.scalars(select(ProcPurchaseOrder).order_by(ProcPurchaseOrder.id.desc()).limit(500)).all()


@router.post("", response_model=PurchaseOrderResponse)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("purchase.write")),
) -> ProcPurchaseOrder:
    existing = db.scalar(
        select(ProcPurchaseOrder).where(
            ProcPurchaseOrder.company_id == payload.company_id,
            ProcPurchaseOrder.po_number == payload.po_number,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="PO number already exists in company")

    po = ProcPurchaseOrder(
        company_id=payload.company_id,
        po_number=payload.po_number,
        supplier_id=payload.supplier_id,
        destination_location_id=payload.destination_location_id,
        currency_code=payload.currency_code,
        payment_terms=payload.payment_terms,
        expected_date=payload.expected_date,
        created_by=user.id,
        status="draft",
    )
    db.add(po)
    db.flush()
    for line in payload.lines:
        db.add(ProcPurchaseOrderLine(po_id=po.id, **line.model_dump(), received_qty=0))
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="proc_purchase_order",
        entity_id=str(po.id),
        action="create",
        before=None,
        after={"po_number": po.po_number, "status": po.status},
    )
    db.commit()
    db.refresh(po)
    return po


@router.post("/{po_id}/confirm")
def confirm_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("purchase.write")),
) -> dict:
    po = db.get(ProcPurchaseOrder, po_id)
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    old_status = po.status
    po.status = "confirmed"
    po.approved_by = user.id

    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="proc_purchase_order",
        entity_id=str(po.id),
        action="confirm",
        before={"status": old_status},
        after={"status": po.status},
    )
    enqueue_outbox_event(
        db,
        event_name="po.confirmed",
        aggregate_type="purchase_order",
        aggregate_id=str(po.id),
        payload={"po_id": po.id, "po_number": po.po_number, "status": po.status},
    )
    db.commit()
    return {"status": po.status}
