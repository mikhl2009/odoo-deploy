from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import and_, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.integration import IntExternalIdMap, IntStoreConnection, IntSyncQueue
from app.models.sales import SalesOrder, SalesOrderLine
from app.services.nshift import NShiftClient
from app.services.wgr import WGRClient
from app.worker import celery_app
from app.ws.manager import ws_manager

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


@celery_app.task(name="app.tasks.nshift.process_queue", bind=True, max_retries=3)
def process_queue(self):  # type: ignore[override]
    """
    Process IntSyncQueue entries with event_type='nshift.print_label'.
    Creates nShift shipments and triggers Cloud Print.
    """
    db = SessionLocal()
    try:
        now = _now()
        pending = db.scalars(
            select(IntSyncQueue).where(
                and_(
                    IntSyncQueue.entity_type == "shipment",
                    IntSyncQueue.event_type == "nshift.print_label",
                    IntSyncQueue.status == "pending",
                    IntSyncQueue.available_at <= now,
                )
            ).limit(20)
        ).all()

        client = NShiftClient()

        for entry in pending:
            payload = entry.payload or {}
            order_id = payload.get("order_id")
            if order_id is None:
                entry.status = "failed"
                entry.last_error = "missing order_id in payload"
                continue

            order = db.get(SalesOrder, order_id)
            if order is None:
                entry.status = "failed"
                entry.last_error = f"SalesOrder {order_id} not found"
                continue

            printer_id = settings.nshift_printer_id
            packed_by = payload.get("packed_by", "system")

            order_lines = db.scalars(
                select(SalesOrderLine).where(SalesOrderLine.order_id == order_id)
            ).all()

            try:
                result = asyncio.run(
                    client.create_shipment_and_print(order, list(order_lines), printer_id, packed_by)
                )
            except Exception as exc:
                entry.retry_count = (entry.retry_count or 0) + 1
                entry.last_error = str(exc)
                if entry.retry_count >= 3:
                    entry.status = "failed"
                logger.warning("nshift process_queue failed for order %d: %s", order_id, exc)
                continue

            tracking = result.get("tracking_number", "")
            shipment_id = result.get("shipment_id", "")

            # Update SalesOrder
            order.status = "shipped"
            order.shipped_at = _now()

            # Try to update WooCommerce or WGR depending on channel_type
            if order.channel_type == "woocommerce" and order.store_connection_id:
                conn = db.get(IntStoreConnection, order.store_connection_id)
                if conn:
                    ext = db.scalar(
                        select(IntExternalIdMap).where(
                            IntExternalIdMap.source_system == "woocommerce",
                            IntExternalIdMap.source_entity == "order",
                            IntExternalIdMap.source_id == order.external_order_id,
                        )
                    )
                    woo_order_id = ext.target_id if ext else order.external_order_id
                    if woo_order_id:
                        try:
                            base_url = conn.api_base_url.rstrip("/")
                            with httpx.Client(timeout=30) as http:
                                http.put(
                                    f"{base_url}/wp-json/wc/v3/orders/{woo_order_id}",
                                    json={"status": "completed"},
                                    auth=(conn.consumer_key, conn.consumer_secret),
                                ).raise_for_status()
                        except Exception as exc:
                            logger.warning("Could not update WooCommerce order %s: %s", woo_order_id, exc)

            elif order.channel_type == "wgr" and order.store_connection_id:
                conn = db.get(IntStoreConnection, order.store_connection_id)
                if conn and order.external_order_id:
                    try:
                        wgr = WGRClient(conn.api_base_url, conn.consumer_key, conn.consumer_secret)
                        asyncio.run(wgr.set_order_status(int(order.external_order_id), 5))
                    except Exception as exc:
                        logger.warning("Could not update WGR order status: %s", exc)

            entry.status = "done"
            entry.processed_at = _now()

            # Broadcast WebSocket
            asyncio.run(
                ws_manager.broadcast(
                    "sync-status",
                    {
                        "event": "label_printed",
                        "order_id": order_id,
                        "tracking": tracking,
                        "shipment_id": shipment_id,
                    },
                )
            )
            asyncio.run(
                ws_manager.broadcast(
                    "warehouse",
                    {
                        "event": "label_printed",
                        "order_id": order_id,
                        "tracking": tracking,
                        "shipment_id": shipment_id,
                    },
                )
            )

        db.commit()

    except Exception as exc:
        db.rollback()
        logger.exception("nshift process_queue unhandled error: %s", exc)
        raise
    finally:
        db.close()
