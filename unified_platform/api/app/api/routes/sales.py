from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.sales import (
    SalesCustomer,
    SalesOrder,
    SalesOrderEvent,
    SalesOrderLine,
    SalesRefund,
    SalesReturn,
    SalesShipment,
)
from app.schemas.sales import (
    CustomerCreate,
    CustomerResponse,
    CustomerTierAssignRequest,
    CustomerUpdate,
    OrderLifecycleAction,
    RefundCreate,
    ReturnCreate,
    SalesOrderCreate,
    SalesOrderResponse,
)
from app.services.audit import enqueue_outbox_event, log_audit_event

router = APIRouter(prefix="/sales", tags=["sales"])


def _add_event(db: Session, *, order_id: int, event_type: str, user_id: int | None, payload: dict | None = None) -> None:
    db.add(SalesOrderEvent(order_id=order_id, event_type=event_type, created_by=user_id, payload=payload))


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sales.read")),
) -> list[SalesCustomer]:
    return db.scalars(select(SalesCustomer).order_by(SalesCustomer.id.desc()).limit(500)).all()


@router.post("/customers", response_model=CustomerResponse)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesCustomer:
    existing = db.scalar(select(SalesCustomer).where(SalesCustomer.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Customer email already exists")
    customer = SalesCustomer(**payload.model_dump(), status="active")
    db.add(customer)
    db.flush()
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="sales_customer",
        entity_id=str(customer.id),
        action="create",
        before=None,
        after={"email": customer.email, "customer_type": customer.customer_type},
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
def patch_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesCustomer:
    customer = db.get(SalesCustomer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    before = {
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "company_name": customer.company_name,
        "phone": customer.phone,
        "credit_limit": str(customer.credit_limit) if customer.credit_limit else None,
        "payment_terms": customer.payment_terms,
        "status": customer.status,
    }
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="sales_customer",
        entity_id=str(customer.id),
        action="update",
        before=before,
        after={
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "company_name": customer.company_name,
            "phone": customer.phone,
            "credit_limit": str(customer.credit_limit) if customer.credit_limit else None,
            "payment_terms": customer.payment_terms,
            "status": customer.status,
        },
    )
    db.commit()
    db.refresh(customer)
    return customer


@router.post("/customers/{customer_id}/tier")
def assign_customer_tier(
    customer_id: int,
    payload: CustomerTierAssignRequest,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sales.write")),
) -> dict:
    customer = db.get(SalesCustomer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer.tier_id = payload.tier_id
    db.commit()
    return {"customer_id": customer.id, "tier_id": customer.tier_id}


@router.get("/orders", response_model=list[SalesOrderResponse])
def list_orders(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sales.read")),
) -> list[SalesOrder]:
    return db.scalars(select(SalesOrder).order_by(SalesOrder.id.desc()).limit(500)).all()


@router.get("/orders/{order_id}", response_model=SalesOrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sales.read")),
) -> SalesOrder:
    order = db.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/orders", response_model=SalesOrderResponse)
def create_order(
    payload: SalesOrderCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesOrder:
    existing = db.scalar(
        select(SalesOrder).where(
            SalesOrder.company_id == payload.company_id,
            SalesOrder.order_number == payload.order_number,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="Order number already exists")

    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for line in payload.lines:
        line_subtotal = (line.quantity * line.unit_price) - line.discount
        subtotal += line_subtotal
        if line.tax_rate:
            tax_total += line_subtotal * (line.tax_rate / Decimal("100"))
    total = subtotal + tax_total + payload.shipping_total

    order = SalesOrder(
        company_id=payload.company_id,
        order_number=payload.order_number,
        channel_type=payload.channel_type,
        store_connection_id=payload.store_connection_id,
        external_order_id=payload.external_order_id,
        customer_id=payload.customer_id,
        warehouse_location_id=payload.warehouse_location_id,
        status="pending",
        currency_code=payload.currency_code,
        subtotal=subtotal,
        tax_total=tax_total,
        shipping_total=payload.shipping_total,
        total=total,
        created_by=user.id,
    )
    db.add(order)
    db.flush()

    for line in payload.lines:
        line_subtotal = (line.quantity * line.unit_price) - line.discount
        line_tax = Decimal("0")
        if line.tax_rate:
            line_tax = line_subtotal * (line.tax_rate / Decimal("100"))
        db.add(
            SalesOrderLine(
                order_id=order.id,
                variant_id=line.variant_id,
                sku_snapshot=line.sku_snapshot,
                name_snapshot=line.name_snapshot,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount=line.discount,
                tax_rate=line.tax_rate,
                line_total=line_subtotal + line_tax,
            )
        )

    _add_event(db, order_id=order.id, event_type="created", user_id=user.id, payload={"status": order.status})
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="sales_order",
        entity_id=str(order.id),
        action="create",
        before=None,
        after={"order_number": order.order_number, "status": order.status, "total": str(order.total)},
    )
    enqueue_outbox_event(
        db,
        event_name="order.created",
        aggregate_type="sales_order",
        aggregate_id=str(order.id),
        payload={"order_id": order.id, "order_number": order.order_number, "status": order.status},
    )
    db.commit()
    db.refresh(order)
    return order


def _transition_order(
    db: Session,
    *,
    order_id: int,
    to_status: str,
    event_type: str,
    user: CoreUser,
    payload: dict | None = None,
) -> SalesOrder:
    order = db.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    old_status = order.status
    order.status = to_status
    now = datetime.now(UTC)
    if to_status == "confirmed":
        order.confirmed_at = now
    elif to_status == "picking":
        order.picked_at = now
    elif to_status == "packed":
        order.packed_at = now
    elif to_status == "shipped":
        order.shipped_at = now
    elif to_status == "delivered":
        order.delivered_at = now

    _add_event(db, order_id=order.id, event_type=event_type, user_id=user.id, payload=payload)
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="sales_order",
        entity_id=str(order.id),
        action=event_type,
        before={"status": old_status},
        after={"status": order.status},
    )
    db.commit()
    db.refresh(order)
    return order


@router.post("/orders/{order_id}/confirm", response_model=SalesOrderResponse)
def confirm_order(
    order_id: int,
    payload: OrderLifecycleAction,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesOrder:
    return _transition_order(db, order_id=order_id, to_status="confirmed", event_type="confirmed", user=user, payload=payload.model_dump())


@router.post("/orders/{order_id}/pick", response_model=SalesOrderResponse)
def pick_order(
    order_id: int,
    payload: OrderLifecycleAction,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesOrder:
    return _transition_order(db, order_id=order_id, to_status="picking", event_type="picked", user=user, payload=payload.model_dump())


@router.post("/orders/{order_id}/pack", response_model=SalesOrderResponse)
def pack_order(
    order_id: int,
    payload: OrderLifecycleAction,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesOrder:
    return _transition_order(db, order_id=order_id, to_status="packed", event_type="packed", user=user, payload=payload.model_dump())


@router.post("/orders/{order_id}/ship", response_model=SalesOrderResponse)
def ship_order(
    order_id: int,
    payload: OrderLifecycleAction,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesOrder:
    order = _transition_order(db, order_id=order_id, to_status="shipped", event_type="shipped", user=user, payload=payload.model_dump())
    shipment = SalesShipment(
        order_id=order.id,
        shipment_number=f"SHP-{order.id}-{int(datetime.now(UTC).timestamp())}",
        status="shipped",
        carrier_name=payload.carrier_name,
        tracking_number=payload.tracking_number,
        shipped_at=datetime.now(UTC),
    )
    db.add(shipment)
    db.commit()
    return order


@router.post("/orders/{order_id}/deliver", response_model=SalesOrderResponse)
def deliver_order(
    order_id: int,
    payload: OrderLifecycleAction,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> SalesOrder:
    return _transition_order(db, order_id=order_id, to_status="delivered", event_type="delivered", user=user, payload=payload.model_dump())


@router.post("/orders/{order_id}/returns")
def create_return(
    order_id: int,
    payload: ReturnCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> dict:
    order = db.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    ret = SalesReturn(
        order_id=order.id,
        return_number=payload.return_number or f"RET-{order.id}-{int(datetime.now(UTC).timestamp())}",
        reason=payload.reason,
        status="requested",
    )
    db.add(ret)
    _add_event(db, order_id=order.id, event_type="return_requested", user_id=user.id, payload={"return_id": ret.return_number})
    db.commit()
    return {"return_id": ret.id, "return_number": ret.return_number, "status": ret.status}


@router.post("/orders/{order_id}/refunds")
def create_refund(
    order_id: int,
    payload: RefundCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sales.write")),
) -> dict:
    order = db.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    refund = SalesRefund(
        order_id=order.id,
        amount=payload.amount,
        currency_code=order.currency_code,
        reason=payload.reason,
        status=payload.status,
        processed_at=datetime.now(UTC),
    )
    db.add(refund)
    _add_event(
        db,
        order_id=order.id,
        event_type="refund_processed",
        user_id=user.id,
        payload={"refund_id": str(refund.id), "amount": str(payload.amount)},
    )
    db.commit()
    return {"refund_id": refund.id, "status": refund.status}
