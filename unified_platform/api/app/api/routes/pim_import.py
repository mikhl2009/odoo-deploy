"""
POST /api/v1/pim/import-from-woo/{connection_id}

Imports products from a WooCommerce store into PIM (PimProduct + PimProductVariant),
seeds InvStockBalance, and registers external ID mappings (IntExternalIdMap).

Usage (Swagger UI or curl):
  POST /api/v1/pim/import-from-woo/1?location_id=1&seed_stock=true
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.integration import IntExternalIdMap, IntStoreChannel, IntStoreConnection
from app.models.inventory import InvStockBalance
from app.models.pim import PimProduct, PimProductVariant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pim", tags=["pim-import"])


@router.post("/import-from-woo/{connection_id}", summary="Import WooCommerce products → PIM")
async def import_from_woo(
    connection_id: int,
    location_id: int = Query(
        default=1,
        description="core_location.id to seed InvStockBalance rows (must already exist in DB)",
    ),
    seed_stock: bool = Query(
        default=True,
        description="Upsert InvStockBalance.on_hand_qty from Woo stock_quantity",
    ),
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("sync.write")),
) -> dict:
    """
    Paginates /wp-json/wc/v3/products and for variable products fetches variations.
    Upserts PimProduct + PimProductVariant per SKU, registers IntExternalIdMap,
    and optionally seeds InvStockBalance from Woo stock_quantity.
    Returns {imported, updated, skipped, total}.
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

    channel = db.get(IntStoreChannel, conn.store_channel_id)
    raw_company_id = channel.company_id if channel else 0

    # Validate company_id — fall back to first active company if the stored value is bad
    from app.models.core import CoreCompany  # noqa: PLC0415
    from sqlalchemy import select as _select  # noqa: PLC0415
    if raw_company_id and db.get(CoreCompany, raw_company_id):
        company_id = raw_company_id
    else:
        first_company = db.scalar(_select(CoreCompany).where(CoreCompany.active.is_(True)).limit(1))
        if not first_company:
            raise HTTPException(status_code=422, detail="No active company found in database.")
        company_id = first_company.id
        logger.warning(
            "Channel %s has invalid company_id=%s, falling back to company_id=%s",
            conn.store_channel_id, raw_company_id, company_id,
        )

    imported = updated = skipped = 0
    auth = (conn.consumer_key, conn.consumer_secret)
    base = conn.api_base_url.rstrip("/")

    async with httpx.AsyncClient(auth=auth, timeout=30, follow_redirects=True) as client:
        page = 1
        while True:
            resp = await client.get(
                f"{base}/wp-json/wc/v3/products",
                params={"per_page": 100, "page": page, "status": "publish"},
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"WooCommerce API error {resp.status_code}: {resp.text[:300]}",
                )
            products = resp.json()
            if not products:
                break

            for woo_prod in products:
                woo_id: int = woo_prod["id"]
                prod_type: str = woo_prod.get("type", "simple")

                # ── Collect variant rows to process ───────────────────────
                woo_variants: list[dict] = []
                if prod_type == "variable":
                    vr = await client.get(
                        f"{base}/wp-json/wc/v3/products/{woo_id}/variations",
                        params={"per_page": 100},
                    )
                    if vr.status_code == 200:
                        woo_variants = vr.json()

                if not woo_variants:
                    # simple / external / grouped → treat parent as single variant
                    woo_variants = [woo_prod]

                for wv in woo_variants:
                    sku: str = (wv.get("sku") or "").strip()
                    if not sku:
                        skipped += 1
                        continue

                    stock_qty = float(wv.get("stock_quantity") or 0)

                    # EAN: try barcode field then meta_data
                    ean: str | None = wv.get("barcode") or None
                    for meta in wv.get("meta_data", []):
                        if meta.get("key") in ("_barcode", "barcode", "_ean", "ean"):
                            ean = str(meta["value"]) or None
                            break

                    # ── Upsert PimProduct ─────────────────────────────────
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
                        db.flush()  # populate pim_prod.id

                    # ── Upsert PimProductVariant ──────────────────────────
                    variant = db.scalars(
                        select(PimProductVariant).where(
                            PimProductVariant.product_id == pim_prod.id,
                            PimProductVariant.sku == sku,
                        )
                    ).first()
                    if not variant:
                        variant = PimProductVariant(product_id=pim_prod.id, sku=sku, ean=ean)
                        db.add(variant)
                        db.flush()  # populate variant.id
                        imported += 1
                    else:
                        if ean and variant.ean != ean:
                            variant.ean = ean
                        updated += 1

                    # ── IntExternalIdMap ──────────────────────────────────
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

                    # ── InvStockBalance ───────────────────────────────────
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

    logger.info(
        "WooImport conn=%d company=%d imported=%d updated=%d skipped=%d location=%d",
        connection_id, company_id, imported, updated, skipped, location_id,
    )
    return {
        "connection_id": connection_id,
        "company_id": company_id,
        "location_id": location_id,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "total": imported + updated,
        "seed_stock": seed_stock,
    }
