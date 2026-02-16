from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.integration import (
    IntStoreChannel,
    IntStoreConnection,
    IntStoreProductSetting,
    IntSyncError,
    IntSyncQueue,
    IntWebhookEvent,
)
from app.models.pim import PimProductVariant
from app.models.sales import SalesCustomer, SalesOrder, SalesOrderEvent, SalesOrderLine
from app.schemas.woo import (
    StoreChannelCreate,
    StoreConnectionCreate,
    StoreConnectionResponse,
    StoreConnectionUpdate,
    WooBulkPricingRequest,
    WooBulkVisibilityRequest,
    WooWebhookOrderPayload,
)
from app.services.audit import enqueue_outbox_event, log_audit_event
from app.ws.manager import ws_manager

router = APIRouter(prefix="/integration/woo", tags=["woo-integration"])


@router.post("/channels")
def create_channel(
    payload: StoreChannelCreate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    channel = IntStoreChannel(**payload.model_dump())
    db.add(channel)
    db.commit()
    return {"id": channel.id, "name": channel.name}


@router.get("/connections", response_model=list[StoreConnectionResponse])
def list_connections(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.read")),
) -> list[IntStoreConnection]:
    return db.scalars(select(IntStoreConnection).order_by(IntStoreConnection.id.desc())).all()


@router.post("/connections", response_model=StoreConnectionResponse)
def create_connection(
    payload: StoreConnectionCreate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> IntStoreConnection:
    connection = IntStoreConnection(**payload.model_dump())
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.patch("/connections/{connection_id}", response_model=StoreConnectionResponse)
def update_connection(
    connection_id: int,
    payload: StoreConnectionUpdate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> IntStoreConnection:
    connection = db.get(IntStoreConnection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(connection, key, value)
    db.commit()
    db.refresh(connection)
    return connection


def _validate_woo_signature(webhook_secret: str | None, body: bytes, signature_header: str | None) -> bool:
    if not webhook_secret:
        return False
    if not signature_header:
        return False
    digest = hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature_header)


@router.post("/webhooks/{connection_id}/orders")
async def ingest_order_webhook(
    connection_id: int,
    request: Request,
    x_wc_webhook_signature: str | None = Header(default=None),
    x_wc_webhook_delivery_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    connection = db.get(IntStoreConnection, connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    raw_body = await request.body()
    payload_json = json.loads(raw_body.decode("utf-8"))
    payload = WooWebhookOrderPayload.model_validate(payload_json)
    external_event_id = x_wc_webhook_delivery_id or f"woo-{payload.id}-{payload.status}"

    existing_event = db.scalar(
        select(IntWebhookEvent).where(
            IntWebhookEvent.provider == "woocommerce",
            IntWebhookEvent.external_event_id == external_event_id,
        )
    )
    if existing_event:
        return {"status": "ignored_duplicate", "event_id": existing_event.id}

    signature_valid = _validate_woo_signature(connection.webhook_secret, raw_body, x_wc_webhook_signature)
    webhook_event = IntWebhookEvent(
        store_connection_id=connection_id,
        provider="woocommerce",
        event_type="order.updated",
        external_event_id=external_event_id,
        signature_valid=signature_valid,
        payload=payload_json,
        status="received",
    )
    db.add(webhook_event)
    db.flush()

    # Map or create customer
    customer = None
    if payload.billing_email:
        customer = db.scalar(select(SalesCustomer).where(SalesCustomer.email == payload.billing_email))
        if not customer:
            customer = SalesCustomer(
                customer_type="b2c",
                email=payload.billing_email,
                first_name=payload.billing_first_name,
                last_name=payload.billing_last_name,
                status="active",
            )
            db.add(customer)
            db.flush()

    company_id = db.scalar(select(IntStoreChannel.company_id).where(IntStoreChannel.id == connection.store_channel_id))
    if not company_id:
        raise HTTPException(status_code=400, detail="Store channel company missing")

    order_number = payload.number or str(payload.id)
    existing_order = db.scalar(
        select(SalesOrder).where(
            SalesOrder.company_id == company_id,
            SalesOrder.order_number == order_number,
        )
    )
    if existing_order:
        existing_order.status = payload.status
        existing_order.total = payload.total or existing_order.total
        existing_order.shipping_total = payload.shipping_total or existing_order.shipping_total
        order = existing_order
    else:
        order = SalesOrder(
            company_id=company_id,
            order_number=order_number,
            channel_type="web",
            store_connection_id=connection_id,
            external_order_id=payload.id,
            customer_id=customer.id if customer else None,
            status=payload.status,
            currency_code=payload.currency,
            subtotal=Decimal("0"),
            tax_total=Decimal("0"),
            shipping_total=payload.shipping_total or Decimal("0"),
            total=payload.total or Decimal("0"),
            created_by=user.id,
        )
        db.add(order)
        db.flush()

        subtotal = Decimal("0")
        for item in payload.line_items:
            variant = None
            if item.sku:
                variant = db.scalar(select(PimProductVariant).where(PimProductVariant.sku == item.sku))
            unit_price = item.price or Decimal("0")
            quantity = Decimal(item.quantity)
            line_total = unit_price * quantity
            subtotal += line_total
            db.add(
                SalesOrderLine(
                    order_id=order.id,
                    variant_id=variant.id if variant else None,
                    sku_snapshot=item.sku,
                    name_snapshot=item.name,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
        order.subtotal = subtotal
        if not payload.total:
            order.total = subtotal + (payload.shipping_total or Decimal("0"))

    db.add(
        SalesOrderEvent(
            order_id=order.id,
            event_type="woo_webhook_ingested",
            created_by=user.id,
            payload={"external_order_id": payload.id, "status": payload.status},
        )
    )
    webhook_event.status = "processed"
    webhook_event.processed_at = datetime.now(UTC)
    connection.last_sync_at = datetime.now(UTC)
    enqueue_outbox_event(
        db,
        event_name="order.created",
        aggregate_type="sales_order",
        aggregate_id=str(order.id),
        payload={"order_id": order.id, "source": "woocommerce", "status": order.status},
    )
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="int_webhook_event",
        entity_id=str(webhook_event.id),
        action="processed",
        before=None,
        after={"provider": "woocommerce", "external_event_id": external_event_id, "order_id": order.id},
    )
    db.commit()

    await ws_manager.broadcast("sync-status", {"event": "woo_webhook_processed", "connection_id": connection_id, "order_id": order.id})
    return {"status": "processed", "order_id": order.id, "signature_valid": signature_valid}


@router.post("/products/bulk-visibility")
def bulk_visibility(
    payload: WooBulkVisibilityRequest,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    changed = 0
    for item in payload.items:
        setting = db.scalar(
            select(IntStoreProductSetting).where(
                IntStoreProductSetting.store_connection_id == payload.store_connection_id,
                IntStoreProductSetting.variant_id == item.variant_id,
            )
        )
        if not setting:
            setting = IntStoreProductSetting(
                store_connection_id=payload.store_connection_id,
                variant_id=item.variant_id,
                visible=item.visible,
            )
            db.add(setting)
        else:
            setting.visible = item.visible

        db.add(
            IntSyncQueue(
                store_connection_id=payload.store_connection_id,
                entity_type="product",
                event_type="visibility.update",
                payload={"variant_id": item.variant_id, "visible": item.visible},
                status="pending",
            )
        )
        changed += 1

    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="int_store_product_setting",
        entity_id=str(payload.store_connection_id),
        action="bulk_visibility",
        before=None,
        after={"items": changed},
    )
    db.commit()
    return {"queued": changed}


@router.post("/products/bulk-pricing")
def bulk_pricing(
    payload: WooBulkPricingRequest,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    changed = 0
    for item in payload.items:
        setting = db.scalar(
            select(IntStoreProductSetting).where(
                IntStoreProductSetting.store_connection_id == payload.store_connection_id,
                IntStoreProductSetting.variant_id == item.variant_id,
            )
        )
        if not setting:
            setting = IntStoreProductSetting(
                store_connection_id=payload.store_connection_id,
                variant_id=item.variant_id,
                web_price=item.web_price,
                visible=True,
            )
            db.add(setting)
        else:
            setting.web_price = item.web_price

        db.add(
            IntSyncQueue(
                store_connection_id=payload.store_connection_id,
                entity_type="product",
                event_type="price.update",
                payload={"variant_id": item.variant_id, "web_price": str(item.web_price)},
                status="pending",
            )
        )
        changed += 1

    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="int_store_product_setting",
        entity_id=str(payload.store_connection_id),
        action="bulk_pricing",
        before=None,
        after={"items": changed},
    )
    db.commit()
    return {"queued": changed}


@router.get("/sync-status")
def woo_sync_status(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.read")),
) -> dict:
    queue_pending = db.scalar(select(func.count(IntSyncQueue.id)).where(IntSyncQueue.status == "pending")) or 0
    queue_failed = db.scalar(select(func.count(IntSyncQueue.id)).where(IntSyncQueue.status == "failed")) or 0
    queue_done = db.scalar(select(func.count(IntSyncQueue.id)).where(IntSyncQueue.status == "done")) or 0
    webhooks_pending = db.scalar(select(func.count(IntWebhookEvent.id)).where(IntWebhookEvent.status == "received")) or 0
    webhooks_processed = db.scalar(select(func.count(IntWebhookEvent.id)).where(IntWebhookEvent.status == "processed")) or 0
    return {
        "queue_pending": int(queue_pending),
        "queue_failed": int(queue_failed),
        "queue_done": int(queue_done),
        "webhooks_pending": int(webhooks_pending),
        "webhooks_processed": int(webhooks_processed),
    }


@router.post("/sync/retry/{queue_id}")
def retry_sync_item(
    queue_id: int,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    queue_item = db.get(IntSyncQueue, queue_id)
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    queue_item.status = "pending"
    queue_item.retry_count += 1
    queue_item.available_at = datetime.now(UTC)
    queue_item.last_error = None

    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="int_sync_queue",
        entity_id=str(queue_item.id),
        action="retry",
        before=None,
        after={"retry_count": queue_item.retry_count, "status": queue_item.status},
    )
    db.commit()
    return {"queue_id": queue_item.id, "status": queue_item.status, "retry_count": queue_item.retry_count}


@router.get("/sync/errors")
def list_sync_errors(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.read")),
) -> list[dict]:
    rows = db.scalars(select(IntSyncError).order_by(IntSyncError.id.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "job_id": row.job_id,
            "queue_id": row.queue_id,
            "error_code": row.error_code,
            "error_message": row.error_message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
