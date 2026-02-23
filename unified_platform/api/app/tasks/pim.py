"""
Celery tasks for PIM operations.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.core import CoreCompany
from app.models.integration import IntExternalIdMap, IntStoreConnection
from app.models.inventory import InvStockBalance
from app.models.pim import PimProduct, PimProductVariant
from app.worker import celery_app

logger = logging.getLogger(__name__)

                       # --- Extract name, brand, price ---
                       name = wv.get("name") or woo_prod.get("name") or sku
                       brand_name = None
                       if "brands" in wv and wv["brands"]:
                           brand_name = wv["brands"][0].get("name")
                       elif "brands" in woo_prod and woo_prod["brands"]:
                           brand_name = woo_prod["brands"][0].get("name")
                       price = wv.get("price") or wv.get("regular_price") or wv.get("sale_price")
                       try:
                           price = float(price) if price is not None else None
                       except Exception:
                           price = None

@celery_app.task(
    name="app.tasks.pim.import_from_woo",
    bind=True,
    max_retries=0,
)
def import_from_woo(self, connection_id: int, location_id: int, seed_stock: bool) -> dict:  # type: ignore[override]
    """
    Import WooCommerce products → PIM.
    Paginates /wp-json/wc/v3/products, fetches variations for variable products,
    upserts PimProduct + PimProductVariant, registers IntExternalIdMap,
    and optionally seeds InvStockBalance.
    Returns {connection_id, company_id, location_id, imported, updated, skipped, total, seed_stock}.
    """
    db = SessionLocal()
                               brand_id=None,
    try:
        conn = db.get(IntStoreConnection, connection_id)
        if not conn:
                       # --- Upsert brand ---
                       if brand_name:
                           brand = db.scalars(
                               select(PimBrand).where(
                                   PimBrand.company_id == company_id,
                                   PimBrand.name == brand_name,
                               )
                           ).first()
                           if not brand:
                               brand = PimBrand(company_id=company_id, name=brand_name, active=True)
                               db.add(brand)
                               db.flush()
                           pim_prod.brand_id = brand.id
                       # --- Upsert product name (I18n) ---
                       if name:
                           prod_i18n = db.scalars(
                               select(PimProductI18n).where(
                                   PimProductI18n.product_id == pim_prod.id,
                                   PimProductI18n.language_code == "sv-SE",
                               )
                           ).first()
                           if not prod_i18n:
                               prod_i18n = PimProductI18n(product_id=pim_prod.id, language_code="sv-SE", name=name)
                               db.add(prod_i18n)
                               db.flush()
                           else:
                               prod_i18n.name = name
            raise ValueError(f"Connection {connection_id} not found")

        if not conn.consumer_key or not conn.consumer_secret:
            raise ValueError(
                "Connection has no consumer_key/consumer_secret. "
                "PATCH /integration/woo/connections/{id} to add credentials."
            )

        from app.models.integration import IntStoreChannel  # noqa: PLC0415
        channel = db.get(IntStoreChannel, conn.store_channel_id)
        raw_company_id = channel.company_id if channel else 0

        if raw_company_id and db.get(CoreCompany, raw_company_id):
            company_id = raw_company_id
        else:
            first_company = db.scalar(
                select(CoreCompany).where(CoreCompany.active.is_(True)).limit(1)
            )
                       # --- Upsert price ---
                       if price is not None:
                           price_list_id = 1  # TODO: select correct pricelist
                           price_item = db.scalars(
                               select(PimPriceListItem).where(
                                   PimPriceListItem.price_list_id == price_list_id,
                                   PimPriceListItem.variant_id == variant.id,
                                   PimPriceListItem.min_qty == 1,
                               )
                           ).first()
                           if not price_item:
                               price_item = PimPriceListItem(
                                   price_list_id=price_list_id,
                                   variant_id=variant.id,
                                   min_qty=1,
                                   unit_price=price,
                               )
                               db.add(price_item)
                               db.flush()
                           else:
                               price_item.unit_price = price
            if not first_company:
                raise ValueError("No active company found in database.")
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
                    raise ValueError(
                        f"WooCommerce API error {resp.status_code}: {resp.text[:300]}"
                    )
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

                        # ── Upsert PimProduct ─────────────────────────────
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

                        # ── Upsert PimProductVariant ──────────────────────
                        variant = db.scalars(
                            select(PimProductVariant).where(
                                PimProductVariant.product_id == pim_prod.id,
                                PimProductVariant.sku == sku,
                            )
                        ).first()
                        if not variant:
                            variant = PimProductVariant(product_id=pim_prod.id, sku=sku, ean=ean)
                            db.add(variant)
                            db.flush()
                            imported += 1
                        else:
                            if ean and variant.ean != ean:
                                variant.ean = ean
                            updated += 1

                        # ── IntExternalIdMap ──────────────────────────────
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

                        # ── InvStockBalance ───────────────────────────────
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
        logger.info(
            "WooImport conn=%d company=%d imported=%d updated=%d skipped=%d location=%d",
            connection_id, company_id, imported, updated, skipped, location_id,
        )
        return result

    except Exception as exc:
        logger.exception("WooImport failed for connection %d: %s", connection_id, exc)
        raise
    finally:
        db.close()
