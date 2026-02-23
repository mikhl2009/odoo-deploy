from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import CoreCompany, CoreLocation
from app.models.integration import IntExternalIdMap, IntStoreChannel, IntStoreConnection
from app.models.inventory import InvStockBalance
from app.models.pim import (
    PimBrand,
    PimPriceList,
    PimPriceListItem,
    PimProduct,
    PimProductI18n,
    PimProductVariant,
)

logger = logging.getLogger(__name__)

_EAN_META_KEYS = {"_barcode", "barcode", "_ean", "ean"}
_BRAND_META_KEYS = {
    "brand",
    "_brand",
    "pa_brand",
    "attribute_pa_brand",
    "product_brand",
    "_product_brand",
}
_BRAND_ATTR_NAMES = {
    "brand",
    "pa_brand",
    "attribute_pa_brand",
    "varumarke",
    "marke",
}


def _clean_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _parse_decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _extract_meta_value(data: dict, keys: set[str]) -> str | None:
    for entry in data.get("meta_data", []):
        key = _clean_text(entry.get("key"))
        if not key:
            continue
        if _normalize_key(key) in keys:
            value = _clean_text(entry.get("value"))
            if value:
                return value
    return None


def _extract_brand_from_attributes(data: dict) -> str | None:
    for attr in data.get("attributes", []):
        name = _clean_text(attr.get("name"))
        if not name or _normalize_key(name) not in _BRAND_ATTR_NAMES:
            continue
        option = _clean_text(attr.get("option")) or _clean_text(attr.get("value"))
        if option:
            return option
    return None


def _extract_name(woo_product: dict, woo_variant: dict, sku: str) -> str:
    return (
        _clean_text(woo_variant.get("name"))
        or _clean_text(woo_product.get("name"))
        or sku
    )


def _extract_descriptions(woo_product: dict, woo_variant: dict) -> tuple[str | None, str | None]:
    short_desc = _clean_text(woo_variant.get("short_description")) or _clean_text(
        woo_product.get("short_description")
    )
    long_desc = _clean_text(woo_variant.get("description")) or _clean_text(
        woo_product.get("description")
    )
    return short_desc, long_desc


def _extract_brand_name(woo_product: dict, woo_variant: dict) -> str | None:
    for source in (woo_variant, woo_product):
        brands = source.get("brands")
        if isinstance(brands, list) and brands:
            first = brands[0]
            if isinstance(first, dict):
                name = _clean_text(first.get("name"))
                if name:
                    return name
            else:
                name = _clean_text(first)
                if name:
                    return name

        brand = source.get("brand")
        if isinstance(brand, dict):
            name = _clean_text(brand.get("name"))
            if name:
                return name
        else:
            name = _clean_text(brand)
            if name:
                return name

        meta_brand = _extract_meta_value(source, _BRAND_META_KEYS)
        if meta_brand:
            return meta_brand

        attr_brand = _extract_brand_from_attributes(source)
        if attr_brand:
            return attr_brand

    return None


def _extract_price(woo_product: dict, woo_variant: dict) -> Decimal | None:
    for source in (woo_variant, woo_product):
        for key in ("price", "regular_price", "sale_price"):
            parsed = _parse_decimal(source.get(key))
            if parsed is not None:
                return parsed
    return None


def _extract_ean(woo_product: dict, woo_variant: dict) -> str | None:
    variant_ean = _clean_text(woo_variant.get("barcode")) or _extract_meta_value(woo_variant, _EAN_META_KEYS)
    if variant_ean:
        return variant_ean
    return _clean_text(woo_product.get("barcode")) or _extract_meta_value(woo_product, _EAN_META_KEYS)


def _resolve_company_id(db: Session, conn: IntStoreConnection) -> int:
    channel = db.get(IntStoreChannel, conn.store_channel_id)
    raw_company_id = channel.company_id if channel else 0
    if raw_company_id and db.get(CoreCompany, raw_company_id):
        return raw_company_id

    first_company = db.scalar(select(CoreCompany).where(CoreCompany.active.is_(True)).limit(1))
    if not first_company:
        raise ValueError("No active company found in database.")

    logger.warning(
        "Channel %s has invalid company_id=%s, falling back to company_id=%s",
        conn.store_channel_id,
        raw_company_id,
        first_company.id,
    )
    return first_company.id


def _ensure_location(
    db: Session,
    *,
    company_id: int,
    location_id: int,
    create_if_missing: bool,
) -> int:
    if not create_if_missing:
        return location_id
    location = db.get(CoreLocation, location_id)
    if location:
        return location_id
    logger.warning("CoreLocation id=%s missing - creating fallback warehouse", location_id)
    location = CoreLocation(
        company_id=company_id,
        code="WH-MAIN",
        name="Huvudlager",
        location_type="warehouse",
        active=True,
    )
    db.add(location)
    db.flush()
    logger.info("Created CoreLocation id=%s", location.id)
    return location.id


def _ensure_woo_pricelist(db: Session, company_id: int) -> PimPriceList:
    existing = db.scalar(
        select(PimPriceList).where(
            PimPriceList.company_id == company_id,
            PimPriceList.channel_type == "woocommerce",
            PimPriceList.active.is_(True),
        )
    )
    if existing:
        return existing

    fallback = db.scalar(
        select(PimPriceList).where(
            PimPriceList.company_id == company_id,
            PimPriceList.name == "Default Retail SEK",
            PimPriceList.active.is_(True),
        )
    )
    if fallback:
        return fallback

    created = PimPriceList(
        company_id=company_id,
        name="WooCommerce Retail SEK",
        channel_type="woocommerce",
        currency_code="SEK",
        active=True,
    )
    db.add(created)
    db.flush()
    return created


def _fetch_variations(client: httpx.Client, base_url: str, woo_product_id: int) -> list[dict]:
    variations: list[dict] = []
    page = 1
    while True:
        response = client.get(
            f"{base_url}/wp-json/wc/v3/products/{woo_product_id}/variations",
            params={"per_page": 100, "page": page},
        )
        if response.status_code != 200:
            logger.warning(
                "Could not fetch variations for Woo product %s: %s",
                woo_product_id,
                response.status_code,
            )
            return []
        chunk = response.json()
        if not chunk:
            break
        variations.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1
    return variations


def run_woo_import(
    db: Session,
    *,
    connection_id: int,
    location_id: int,
    seed_stock: bool,
    create_location_if_missing: bool = False,
) -> dict:
    conn = db.get(IntStoreConnection, connection_id)
    if not conn:
        raise ValueError(f"Connection {connection_id} not found")
    if not conn.consumer_key or not conn.consumer_secret:
        raise ValueError(
            "Connection has no consumer_key/consumer_secret. "
            "PATCH /integration/woo/connections/{id} to add credentials."
        )
    if not conn.api_base_url:
        raise ValueError(f"Connection {connection_id} has no api_base_url")

    company_id = _resolve_company_id(db, conn)
    if seed_stock:
        location_id = _ensure_location(
            db,
            company_id=company_id,
            location_id=location_id,
            create_if_missing=create_location_if_missing,
        )

    imported = 0
    updated = 0
    skipped = 0
    names_synced = 0
    brands_synced = 0
    prices_synced = 0
    seeded_variants: set[int] = set()
    brand_cache: dict[str, PimBrand] = {}

    price_list = _ensure_woo_pricelist(db, company_id)
    base = conn.api_base_url.rstrip("/")
    auth = (conn.consumer_key, conn.consumer_secret)

    with httpx.Client(auth=auth, timeout=30, follow_redirects=True) as client:
        page = 1
        while True:
            response = client.get(
                f"{base}/wp-json/wc/v3/products",
                params={"per_page": 100, "page": page, "status": "publish"},
            )
            if response.status_code != 200:
                raise ValueError(
                    f"WooCommerce API error {response.status_code}: {response.text[:300]}"
                )

            products = response.json()
            if not products:
                break

            for woo_product in products:
                woo_id = int(woo_product["id"])
                product_type = str(woo_product.get("type", "simple"))
                woo_variants = (
                    _fetch_variations(client, base, woo_id)
                    if product_type == "variable"
                    else []
                )
                if not woo_variants:
                    woo_variants = [woo_product]

                for woo_variant in woo_variants:
                    sku = _clean_text(woo_variant.get("sku"))
                    if not sku:
                        skipped += 1
                        continue

                    stock_qty = float(woo_variant.get("stock_quantity") or 0)
                    ean = _extract_ean(woo_product, woo_variant)
                    name = _extract_name(woo_product, woo_variant, sku)
                    brand_name = _extract_brand_name(woo_product, woo_variant)
                    short_desc, long_desc = _extract_descriptions(woo_product, woo_variant)
                    price = _extract_price(woo_product, woo_variant)

                    pim_product = db.scalar(
                        select(PimProduct).where(
                            PimProduct.company_id == company_id,
                            PimProduct.sku == sku,
                        )
                    )
                    if not pim_product:
                        pim_product = PimProduct(
                            company_id=company_id,
                            sku=sku,
                            product_type="variable" if product_type == "variable" else "simple",
                            status="active",
                        )
                        db.add(pim_product)
                        db.flush()

                    if brand_name:
                        brand_key = _normalize_key(brand_name)
                        brand = brand_cache.get(brand_key)
                        if not brand:
                            brand = db.scalar(
                                select(PimBrand).where(
                                    PimBrand.company_id == company_id,
                                    PimBrand.name == brand_name,
                                )
                            )
                            if not brand:
                                brand = PimBrand(
                                    company_id=company_id,
                                    name=brand_name,
                                    active=True,
                                )
                                db.add(brand)
                                db.flush()
                            brand_cache[brand_key] = brand
                        if pim_product.brand_id != brand.id:
                            pim_product.brand_id = brand.id
                            brands_synced += 1

                    translation = db.scalar(
                        select(PimProductI18n).where(
                            PimProductI18n.product_id == pim_product.id,
                            PimProductI18n.language_code == "sv-SE",
                        )
                    )
                    if not translation:
                        translation = PimProductI18n(
                            product_id=pim_product.id,
                            language_code="sv-SE",
                            name=name,
                            short_desc=short_desc,
                            long_desc=long_desc,
                        )
                        db.add(translation)
                        db.flush()
                        names_synced += 1
                    else:
                        changed = False
                        if name and translation.name != name:
                            translation.name = name
                            changed = True
                        if short_desc is not None and translation.short_desc != short_desc:
                            translation.short_desc = short_desc
                            changed = True
                        if long_desc is not None and translation.long_desc != long_desc:
                            translation.long_desc = long_desc
                            changed = True
                        if changed:
                            names_synced += 1

                    variant = db.scalar(
                        select(PimProductVariant).where(
                            PimProductVariant.product_id == pim_product.id,
                            PimProductVariant.sku == sku,
                        )
                    )
                    if not variant:
                        variant = PimProductVariant(product_id=pim_product.id, sku=sku, ean=ean)
                        db.add(variant)
                        db.flush()
                        imported += 1
                    else:
                        if ean and variant.ean != ean:
                            variant.ean = ean
                        updated += 1

                    if price is not None:
                        price_item = db.scalar(
                            select(PimPriceListItem).where(
                                PimPriceListItem.price_list_id == price_list.id,
                                PimPriceListItem.variant_id == variant.id,
                                PimPriceListItem.min_qty == 1,
                            )
                        )
                        numeric_price = float(price)
                        if not price_item:
                            db.add(
                                PimPriceListItem(
                                    price_list_id=price_list.id,
                                    variant_id=variant.id,
                                    min_qty=1,
                                    unit_price=numeric_price,
                                )
                            )
                            prices_synced += 1
                        elif Decimal(str(price_item.unit_price)) != price:
                            price_item.unit_price = numeric_price
                            prices_synced += 1

                    source_system = f"woocommerce:{connection_id}"
                    source_id = str(woo_variant.get("id") or woo_id)
                    existing_map = db.scalar(
                        select(IntExternalIdMap).where(
                            IntExternalIdMap.source_system == source_system,
                            IntExternalIdMap.source_entity == "product",
                            IntExternalIdMap.source_id == source_id,
                            IntExternalIdMap.target_entity == "variant",
                        )
                    )
                    if not existing_map:
                        db.add(
                            IntExternalIdMap(
                                source_system=source_system,
                                source_entity="product",
                                source_id=source_id,
                                target_entity="variant",
                                target_id=str(variant.id),
                            )
                        )

                    if seed_stock and variant.id not in seeded_variants:
                        seeded_variants.add(variant.id)
                        balance = db.scalar(
                            select(InvStockBalance).where(
                                InvStockBalance.company_id == company_id,
                                InvStockBalance.location_id == location_id,
                                InvStockBalance.variant_id == variant.id,
                                InvStockBalance.lot_id.is_(None),
                                InvStockBalance.container_id.is_(None),
                            )
                        )
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
        "names_synced": names_synced,
        "brands_synced": brands_synced,
        "prices_synced": prices_synced,
        "price_list_id": price_list.id,
    }
    logger.info(
        "WooImport conn=%d company=%d imported=%d updated=%d skipped=%d names=%d brands=%d prices=%d",
        connection_id,
        company_id,
        imported,
        updated,
        skipped,
        names_synced,
        brands_synced,
        prices_synced,
    )
    return result
