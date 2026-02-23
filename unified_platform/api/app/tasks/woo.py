from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import and_, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.integration import IntExternalIdMap, IntStoreConnection, IntSyncError, IntSyncQueue
from app.worker import celery_app

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=UTC)


@celery_app.task(name="app.tasks.woo.push_stock", bind=True, max_retries=3)
def push_stock(self):  # type: ignore[override]
    """
    Process IntSyncQueue entries with event_type='stock.push'.
    Push stock updates to WooCommerce via REST API.
    """
    db = SessionLocal()
    try:
        now = _now()
        pending = db.scalars(
            select(IntSyncQueue).where(
                and_(
                    IntSyncQueue.entity_type == "stock",
                    IntSyncQueue.event_type == "stock.push",
                    IntSyncQueue.status == "pending",
                    IntSyncQueue.available_at <= now,
                )
            ).limit(settings.woo_push_batch_size)
        ).all()

        success = 0
        failed = 0

        for entry in pending:
            payload = entry.payload or {}
            sku = payload.get("sku")
            qty = payload.get("qty")

            if sku is None or qty is None:
                entry.status = "failed"
                entry.last_error = "missing sku or qty in payload"
                failed += 1
                continue

            conn = db.get(IntStoreConnection, entry.store_connection_id)
            if conn is None or not conn.active:
                entry.status = "failed"
                entry.last_error = "connection not found or inactive"
                failed += 1
                continue

            try:
                woo_product_id = _resolve_woo_product_id(db, conn, sku)
                if woo_product_id is None:
                    raise ValueError(f"WooCommerce product not found for SKU '{sku}'")

                base_url = conn.api_base_url.rstrip("/")
                with httpx.Client(timeout=30) as client:
                    resp = client.put(
                        f"{base_url}/wp-json/wc/v3/products/{woo_product_id}",
                        json={"stock_quantity": qty, "manage_stock": True},
                        auth=(conn.consumer_key, conn.consumer_secret),
                    )
                    resp.raise_for_status()

                entry.status = "done"
                entry.processed_at = _now()
                success += 1

            except Exception as exc:
                entry.retry_count = (entry.retry_count or 0) + 1
                entry.last_error = str(exc)
                if entry.retry_count >= 3:
                    entry.status = "failed"
                    db.add(
                        IntSyncError(
                            queue_id=entry.id,
                            error_message=str(exc),
                            payload=payload,
                        )
                    )
                    failed += 1
                # else: leave as pending for next run
                logger.warning("push_stock failed for queue %d sku=%s: %s", entry.id, sku, exc)

        db.commit()
        logger.info("push_stock: success=%d failed=%d", success, failed)

    except Exception as exc:
        db.rollback()
        logger.exception("push_stock unhandled error: %s", exc)
        raise
    finally:
        db.close()


def _resolve_woo_product_id(db, conn: IntStoreConnection, sku: str) -> int | None:
    """
    Look up (and cache) the WooCommerce product ID for a given SKU.
    Uses IntExternalIdMap as a cache keyed by source_system='woocommerce',
    source_entity='sku', source_id='{conn.id}:{sku}'.
    """
    lookup_key = f"{conn.id}:{sku}"
    existing = db.scalar(
        select(IntExternalIdMap).where(
            IntExternalIdMap.source_system == "woocommerce",
            IntExternalIdMap.source_entity == "sku",
            IntExternalIdMap.source_id == lookup_key,
        )
    )
    if existing:
        return int(existing.target_id)

    # Fetch from WooCommerce
    base_url = conn.api_base_url.rstrip("/")
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{base_url}/wp-json/wc/v3/products",
            params={"sku": sku},
            auth=(conn.consumer_key, conn.consumer_secret),
        )
        resp.raise_for_status()
        products = resp.json()

    if not products:
        return None

    woo_id = products[0].get("id")
    if woo_id is None:
        return None

    # Cache it
    db.add(
        IntExternalIdMap(
            source_system="woocommerce",
            source_entity="sku",
            source_id=lookup_key,
            target_entity="woo_product_id",
            target_id=str(woo_id),
        )
    )
    db.flush()
    return int(woo_id)
