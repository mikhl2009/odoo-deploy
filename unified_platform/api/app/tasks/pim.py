"""
Celery tasks for PIM operations.
"""
from __future__ import annotations

import logging

from app.db.session import SessionLocal
from app.services.pim_import import run_woo_import
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.pim.import_from_woo",
    bind=True,
    max_retries=0,
)
def import_from_woo(self, connection_id: int, location_id: int, seed_stock: bool) -> dict:  # type: ignore[override]
    """
    Import WooCommerce catalog and stock into PIM/Inventory.
    """
    db = SessionLocal()
    try:
        result = run_woo_import(
            db,
            connection_id=connection_id,
            location_id=location_id,
            seed_stock=seed_stock,
            create_location_if_missing=True,
        )
        logger.info(
            "WooImport conn=%d imported=%d updated=%d skipped=%d names=%d brands=%d prices=%d",
            connection_id,
            result.get("imported", 0),
            result.get("updated", 0),
            result.get("skipped", 0),
            result.get("names_synced", 0),
            result.get("brands_synced", 0),
            result.get("prices_synced", 0),
        )
        return result
    except Exception as exc:
        logger.exception("WooImport failed for connection %d: %s", connection_id, exc)
        raise
    finally:
        db.close()
