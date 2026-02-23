from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.integration import IntExternalIdMap, IntStoreConnection, IntSyncQueue
from app.models.inventory import InvStockBalance, InvStockMovement
from app.models.pim import PimProductVariant
from app.models.sales import SalesOrder, SalesOrderLine
from app.services.wgr import WGRClient
from app.worker import celery_app
from app.ws.manager import ws_manager

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# poll_stock
# ---------------------------------------------------------------------------


@celery_app.task(name="app.tasks.wgr.poll_stock", bind=True, max_retries=3)
def poll_stock(self):  # type: ignore[override]
    """
    Poll WGR for stock changes since last_sync_at.
    Updates InvStockBalance and InvStockMovement, then enqueues stock.push for
    every active WooCommerce connection.
    """
    db = SessionLocal()
    try:
        wgr_connections = db.scalars(
            select(IntStoreConnection).where(
                IntStoreConnection.provider == "wgr",
                IntStoreConnection.active.is_(True),
            )
        ).all()

        woo_connections = db.scalars(
            select(IntStoreConnection).where(
                IntStoreConnection.provider == "woocommerce",
                IntStoreConnection.active.is_(True),
            )
        ).all()

        total_updated = 0

        for conn in wgr_connections:
            client = WGRClient(conn.api_base_url, conn.consumer_key, conn.consumer_secret)
            last_sync = conn.last_sync_at
            updated_from = last_sync if isinstance(last_sync, datetime) else None

            try:
                stock_items = asyncio.run(client.get_stock(updated_from=updated_from))
            except Exception as exc:
                logger.error("WGR poll_stock failed for conn %d: %s", conn.id, exc)
                try:
                    raise self.retry(exc=exc, countdown=60)
                except self.MaxRetriesExceededError:
                    continue

            for item in stock_items:
                sku = item.get("articleNumber", "")
                qty = int(item.get("stock", 0))
                if not sku:
                    continue

                variant = db.scalar(
                    select(PimProductVariant).where(PimProductVariant.sku == sku)
                )
                if variant is None:
                    logger.debug("WGR stock: no variant for SKU '%s', skipping", sku)
                    continue

                # Upsert InvStockBalance
                balance = db.scalar(
                    select(InvStockBalance).where(
                        InvStockBalance.variant_id == variant.id,
                        InvStockBalance.location_id == conn.store_channel_id,  # best-effort location mapping
                        InvStockBalance.lot_id.is_(None),
                        InvStockBalance.container_id.is_(None),
                    )
                )
                if balance is None:
                    balance = InvStockBalance(
                        company_id=1,
                        location_id=conn.store_channel_id,
                        variant_id=variant.id,
                        on_hand_qty=qty,
                        reserved_qty=0,
                        available_qty=qty,
                    )
                    db.add(balance)
                else:
                    balance.on_hand_qty = qty
                    balance.available_qty = max(0, qty - float(balance.reserved_qty))

                movement = InvStockMovement(
                    company_id=1,
                    movement_type="wgr_sync",
                    variant_id=variant.id,
                    qty=qty,
                    source_doc_type="wgr",
                    source_doc_id=str(conn.id),
                )
                db.add(movement)

                # Enqueue stock.push for every Woo connection
                for woo in woo_connections:
                    queue_entry = IntSyncQueue(
                        store_connection_id=woo.id,
                        entity_type="stock",
                        event_type="stock.push",
                        payload={"sku": sku, "qty": qty, "variant_id": variant.id},
                        status="pending",
                    )
                    db.add(queue_entry)

                total_updated += 1

            conn.last_sync_at = _now()

        db.commit()
        logger.info("WGR poll_stock: %d articles updated", total_updated)

        # Broadcast WebSocket
        asyncio.run(
            ws_manager.broadcast(
                "sync-status",
                {"event": "wgr_stock_synced", "updated": total_updated},
            )
        )
    except Exception as exc:
        db.rollback()
        logger.exception("poll_stock unhandled error: %s", exc)
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# poll_orders
# ---------------------------------------------------------------------------


@celery_app.task(name="app.tasks.wgr.poll_orders", bind=True, max_retries=3)
def poll_orders(self):  # type: ignore[override]
    """
    Poll WGR for new orders since last_sync_at.
    Creates SalesOrder + SalesOrderLines, decrements stock, enqueues label print.
    """
    db = SessionLocal()
    try:
        wgr_connections = db.scalars(
            select(IntStoreConnection).where(
                IntStoreConnection.provider == "wgr",
                IntStoreConnection.active.is_(True),
            )
        ).all()

        woo_connections = db.scalars(
            select(IntStoreConnection).where(
                IntStoreConnection.provider == "woocommerce",
                IntStoreConnection.active.is_(True),
            )
        ).all()

        for conn in wgr_connections:
            client = WGRClient(conn.api_base_url, conn.consumer_key, conn.consumer_secret)
            last_sync = conn.last_sync_at
            from_time = last_sync if isinstance(last_sync, datetime) else None

            try:
                orders = asyncio.run(client.get_orders(from_time=from_time))
            except Exception as exc:
                logger.error("WGR poll_orders failed for conn %d: %s", conn.id, exc)
                try:
                    raise self.retry(exc=exc, countdown=60)
                except self.MaxRetriesExceededError:
                    continue

            for wgr_order in orders:
                wgr_order_id = wgr_order.get("id")
                if wgr_order_id is None:
                    continue

                # Check duplicate via IntExternalIdMap
                existing = db.scalar(
                    select(IntExternalIdMap).where(
                        IntExternalIdMap.source_system == "wgr",
                        IntExternalIdMap.source_entity == "order",
                        IntExternalIdMap.source_id == str(wgr_order_id),
                    )
                )
                if existing:
                    continue

                # Build SalesOrder
                shipping = (wgr_order.get("client") or {}).get("shippingAddress") or {}
                order = SalesOrder(
                    company_id=1,
                    order_number=f"WGR-{wgr_order_id}",
                    channel_type="wgr",
                    store_connection_id=conn.id,
                    external_order_id=str(wgr_order_id),
                    status="confirmed",
                    currency_code="SEK",
                    subtotal=0,
                    tax_total=0,
                    shipping_total=0,
                    total=0,
                )
                db.add(order)
                db.flush()  # get order.id

                subtotal = 0.0
                for idx, item in enumerate(wgr_order.get("items", []), start=1):
                    sku = item.get("articleNumber", "")
                    qty = float(item.get("quantity", 1))
                    price = float(item.get("price", 0))
                    name = item.get("description", sku)
                    line_total = qty * price

                    variant = db.scalar(
                        select(PimProductVariant).where(PimProductVariant.sku == sku)
                    ) if sku else None

                    line = SalesOrderLine(
                        order_id=order.id,
                        variant_id=variant.id if variant else None,
                        sku_snapshot=sku,
                        name_snapshot=name,
                        quantity=qty,
                        unit_price=price,
                        line_total=line_total,
                    )
                    db.add(line)
                    subtotal += line_total

                    # Decrement stock
                    if variant:
                        balance = db.scalar(
                            select(InvStockBalance).where(
                                InvStockBalance.variant_id == variant.id,
                                InvStockBalance.lot_id.is_(None),
                                InvStockBalance.container_id.is_(None),
                            )
                        )
                        if balance:
                            balance.on_hand_qty = max(0, float(balance.on_hand_qty) - qty)
                            balance.available_qty = max(0, float(balance.available_qty) - qty)

                        movement = InvStockMovement(
                            company_id=1,
                            movement_type="sale",
                            variant_id=variant.id,
                            qty=qty,
                            source_doc_type="wgr_order",
                            source_doc_id=str(wgr_order_id),
                        )
                        db.add(movement)

                order.subtotal = subtotal
                order.total = subtotal

                # External ID mapping
                ext_map = IntExternalIdMap(
                    source_system="wgr",
                    source_entity="order",
                    source_id=str(wgr_order_id),
                    target_entity="sales_order",
                    target_id=str(order.id),
                )
                db.add(ext_map)

                db.flush()

                # Enqueue stock.push for all Woo connections
                for woo in woo_connections:
                    db.add(
                        IntSyncQueue(
                            store_connection_id=woo.id,
                            entity_type="stock",
                            event_type="stock.push",
                            payload={"order_id": order.id, "source": "wgr_order"},
                            status="pending",
                        )
                    )

                # Enqueue nShift label print
                db.add(
                    IntSyncQueue(
                        entity_type="shipment",
                        event_type="nshift.print_label",
                        payload={
                            "order_id": order.id,
                            "channel_type": "wgr",
                        },
                        status="pending",
                    )
                )

                # Mark WGR order as "processing" (status 2)
                try:
                    asyncio.run(client.set_order_status(wgr_order_id, 2))
                except Exception as exc:
                    logger.warning("Could not set WGR order status for %s: %s", wgr_order_id, exc)

            conn.last_sync_at = _now()

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("poll_orders unhandled error: %s", exc)
        raise
    finally:
        db.close()
