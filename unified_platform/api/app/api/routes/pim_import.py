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

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.db.session import SessionLocal
from app.models.core import CoreCompany, CoreUser
from app.models.integration import IntExternalIdMap, IntStoreChannel, IntStoreConnection
from app.models.inventory import InvStockBalance
from app.models.pim import PimProduct, PimProductVariant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pim", tags=["pim-import"])

# In-memory task store - lost on restart, sufficient for demo
_tasks: dict[str, dict[str, Any]] = {}


def _run_import(task_id: str, connection_id: int, location_id: int, seed_stock: bool) -> None:
    """Import WooCommerce products into PIM in a background thread."""
    _tasks[task_id] = {"status": "running"}
    db = SessionLocal()
    try:
        conn = db.get(IntStoreConnection, connection_id)
        if not conn:
            _tasks[task_id] = {"status": "failure", "error": f"Connection {connection_id} not found"}
            return

        channel = db.get(IntStoreChannel, conn.store_channel_id)
        raw_company_id = channel.company_id if channel else 0

        if raw_company_id and db.get(CoreCompany, raw_company_id):
            company_id = raw_company_id
        else:
            first_company = db.scalar(
                select(CoreCompany).where(CoreCompany.active.is_(True)).limit(1)
            )
            if not first_company:
                _tasks[task_id] = {"status": "failure", "error": "No active company in database"}
                return
            company_id = first_company.id
            logger.warning(
                "Channel %s has invalid company_id=%s, falling back to company_id=%s",
                conn.store_channel_id, raw_company_id, company_id,
            )

        imported = updated = skipped = 0
        auth = (conn.consumer_key, conn.consumer_secret)
        base = conn.api_base_url.rstrip("/")

        with httpx.Client(auth=auth, timeout=30, follow_redirects=True) as client:
            page = 1
            while True:
                resp = client.get(
                    f"{base}/wp-json/wc/v3/products",
                    params={"per_page": 100, "page": page, "status": "publish"},
                )
                if resp.status_code != 200:
                    _tasks[task_id] = {
                        "status": "failure",
                        "error": f"WooCommerce API error {resp.status_code}: {resp.text[:300]}",
                    }
                    return
                products = resp.json()
                if not products:
                    break

                for woo_prod in products:
                    woo_id: int = woo_prod["id"]
                    prod_type: str = woo_prod.get("type", "simple")

                    woo_variants: list[dict] = []
                    if prod_type == "variable":
                        vr = client.get(
                            f"{base}/wp-json/wc/v3/products/{woo_id}/variations",
                            params={"per_page": 100},
                        )
                        if vr.status_code == 200:
                            woo_variants = vr.json()

                    if not woo_variants:
                        woo_variants = [woo_prod]

                    for wv in woo_variants:
                        sku: str = (wv.get("sku") or "").strip()
                        if not sku:
                            skipped += 1
                            continue

                        stock_qty = float(wv.get("stock_quantity") or 0)

                        ean: str | None = wv.get("barcode") or None
                        for meta in wv.get("meta_data", []):
                            if meta.get("key") in ("_barcode", "barcode", "_ean", "ean"):
                                ean = str(meta["value"]) or None
                                break

                        # -- Upsert PimProduct
                        pim_prod = db.scalars(
                            select(PimProduct).where(
                                PimProduct.company_id == company_id,
                                PimProduct.sku == sku,
                            )
                        ).first()
                        if not pim_prod:
                            internal_type = "variable" if prod_type == "variable" else "simple"
                            pim_prod = PimProduct(
                                company_id=company_id,
                                sku=sku,
                                product_type=internal_type,
                                status="active",
                            )
                            db.add(pim_prod)
                            db.flush()

                        # -- Upsert PimProductVariant
                        variant = db.scalars(
                            select(PimProductVariant).where(
                                PimProductVariant.product_id == pim_prod.id,
                                PimProductVariant.sku == sku,
                            )
                        ).first()
                        if not variant:
                            variant = PimProductVariant(
                                product_id=pim_prod.id, sku=sku, ean=ean
                            )
                            db.add(variant)
                            db.flush()
                            imported += 1
                        else:
                            if ean and variant.ean != ean:
                                variant.ean = ean
                            updated += 1

                        # -- IntExternalIdMap
                        source_system = f"woocommerce:{connection_id}"
                        existing_map = db.scalars(
                            select(IntExternalIdMap).where(
                                IntExternalIdMap.source_system == source_system,
                                IntExternalIdMap.source_entity == "product",
                                IntExternalIdMap.source_id == str(wv["id"]),
                                IntExternalIdMap.target_entity == "variant",
                            )
                        ).first()
                        if not existing_map:
                            db.add(
                                IntExternalIdMap(
                                    source_system=source_system,
                                    source_entity="product",
                                    source_id=str(wv["id"]),
                                    target_entity="variant",
                                    target_id=str(variant.id),
                                )
                            )

                        # -- InvStockBalance
                        if seed_stock:
                            balance = db.scalars(
                                select(InvStockBalance).where(
                                    InvStockBalance.company_id == company_id,
                                    InvStockBalance.location_id == location_id,
                                    InvStockBalance.variant_id == variant.id,
                                    InvStockBalance.lot_id.is_(None),
                                    InvStockBalance.container_id.is_(None),
                                )
                            ).first()
                            if balance:
                                balance.on_hand_qty = stock_qty
                                balance.available_qty = stock_qty
                            else:
                                db.add(
                                    InvStockBalance(
                                        company_id=company_id,
                                        location_id=location_id,
                                        variant_id=variant.id,
                                        on_hand_qty=stock_qty,
                                        available_qty=stock_qty,
                                        reserved_qty=0,
                                    )
                                )

                db.commit()

                if len(products) < 100:
                    break
                page += 1

        result = {
            "connection_id": connection_id,
            "company_id": company_id,
            "location_id": location_id,
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "total": imported + updated,
            "seed_stock": seed_stock,
        }
        _tasks[task_id] = {"status": "success", "result": result}
        logger.info(
            "WooImport task=%s conn=%d company=%d imported=%d updated=%d skipped=%d",
            task_id, connection_id, company_id, imported, updated, skipped,
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
