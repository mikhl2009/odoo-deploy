#!/usr/bin/env python3
"""Reconcile WooCommerce stock quantities into Odoo for pack-based catalogs.

Rules:
- For multipack templates (1/5/10-pack etc.), keep stock only on 1-pack variants.
- For all other storable Woo products, set stock to Woo stock quantity.
- Write stock to a target warehouse stock location (default: SH/Lager).
"""

from __future__ import annotations

import argparse
import re
import xmlrpc.client
from collections import defaultdict


DEFAULT_URL = "https://snushallen.cloud"
DEFAULT_DB = "odoo"
DEFAULT_USER = "mikael@snussidan.se"
DEFAULT_PASSWORD = "a04315610102c5d4cde37f7c8afea09d8721569a"
DEFAULT_WAREHOUSE_CODE = "SH"


PACK_RE = re.compile(r"(?:^|\D)(\d+)\s*[- ]?pack(?:\b|$)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile Woo stock to Odoo stock")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--warehouse-code", default=DEFAULT_WAREHOUSE_CODE)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def connect(url: str, db: str, user: str, password: str):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise SystemExit("Authentication failed.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models


def pack_size_from_text(text: str | None) -> int | None:
    if not text:
        return None
    match = PACK_RE.search(text.lower())
    if match:
        return int(match.group(1))
    return None


def main() -> int:
    args = parse_args()
    uid, models = connect(args.url, args.db, args.user, args.password)

    wh_ids = models.execute_kw(
        args.db,
        uid,
        args.password,
        "stock.warehouse",
        "search",
        [[["code", "=", args.warehouse_code]]],
        {"limit": 1},
    )
    if not wh_ids:
        raise SystemExit(f"No warehouse found with code={args.warehouse_code}")
    warehouse = models.execute_kw(
        args.db,
        uid,
        args.password,
        "stock.warehouse",
        "read",
        [wh_ids],
        {"fields": ["id", "name", "code", "lot_stock_id"]},
    )[0]
    lot_stock_location_id = warehouse["lot_stock_id"][0]

    internal_locations = models.execute_kw(
        args.db,
        uid,
        args.password,
        "stock.location",
        "search_read",
        [[["usage", "=", "internal"]]],
        {"fields": ["id"], "limit": 10000},
    )
    internal_location_ids = {loc["id"] for loc in internal_locations}

    products = models.execute_kw(
        args.db,
        uid,
        args.password,
        "product.product",
        "search_read",
        [[["active", "=", True], ["product_tmpl_id.source", "=", "WooCommerce"], ["is_storable", "=", True]]],
        {
            "fields": [
                "id",
                "display_name",
                "default_code",
                "product_tmpl_id",
                "woocommerce_id",
                "woocommerce_stock_quantity",
                "qty_available",
            ],
            "limit": 20000,
        },
    )

    by_template: dict[int, list[dict]] = defaultdict(list)
    for product in products:
        template_id = product["product_tmpl_id"][0]
        by_template[template_id].append(product)

    template_ids = list(by_template.keys())
    template_map = {}
    if template_ids:
        templates = models.execute_kw(
            args.db,
            uid,
            args.password,
            "product.template",
            "read",
            [template_ids],
            {"fields": ["id", "woocommerce_stock_quantity"]},
        )
        template_map = {template["id"]: template for template in templates}

    all_product_ids = [product["id"] for product in products]
    quant_ids = models.execute_kw(
        args.db,
        uid,
        args.password,
        "stock.quant",
        "search",
        [[["product_id", "in", all_product_ids], ["location_id.usage", "=", "internal"]]],
        {"limit": 200000},
    )
    quant_map: dict[int, list[dict]] = defaultdict(list)
    if quant_ids:
        quants = models.execute_kw(
            args.db,
            uid,
            args.password,
            "stock.quant",
            "read",
            [quant_ids],
            {"fields": ["id", "product_id", "location_id", "quantity", "lot_id", "package_id", "owner_id"]},
        )
        for quant in quants:
            product_id = quant["product_id"][0]
            quant_map[product_id].append(quant)

    desired_qty_by_product: dict[int, float] = {}
    multipack_templates = 0
    for template_id, variants in by_template.items():
        template_stock_qty = float((template_map.get(template_id) or {}).get("woocommerce_stock_quantity") or 0.0)

        def stock_source_qty(variant: dict) -> float:
            variant_stock = float(variant.get("woocommerce_stock_quantity") or 0.0)
            if variant_stock:
                return variant_stock
            # For simple products, Woo stock often exists only on product.template.
            if not variant.get("woocommerce_id"):
                return template_stock_qty
            return variant_stock

        pack_sizes = {}
        for variant in variants:
            pack_sizes[variant["id"]] = pack_size_from_text(variant.get("display_name"))

        has_one_pack = any(size == 1 for size in pack_sizes.values())
        has_multi_pack = any((size or 0) > 1 for size in pack_sizes.values())

        if has_one_pack and has_multi_pack:
            multipack_templates += 1
            one_pack_variant = next((variant for variant in variants if pack_sizes[variant["id"]] == 1), None)
            if one_pack_variant:
                one_pack_qty = stock_source_qty(one_pack_variant)
                for variant in variants:
                    desired_qty_by_product[variant["id"]] = one_pack_qty if variant["id"] == one_pack_variant["id"] else 0.0
                continue

        for variant in variants:
            desired_qty_by_product[variant["id"]] = stock_source_qty(variant)

    writes = 0
    creates = 0
    skipped_negative = 0

    for product in products:
        product_id = product["id"]
        desired_total = desired_qty_by_product.get(product_id, 0.0)
        quants_for_product = quant_map.get(product_id, [])

        other_internal_qty = 0.0
        target_quant = None
        for quant in quants_for_product:
            location_id = quant["location_id"][0]
            if location_id not in internal_location_ids:
                continue
            if location_id == lot_stock_location_id and not quant["lot_id"] and not quant["package_id"] and not quant["owner_id"]:
                target_quant = quant
            else:
                other_internal_qty += float(quant["quantity"] or 0.0)

        target_qty = desired_total - other_internal_qty
        if target_qty < 0:
            target_qty = 0.0
            skipped_negative += 1

        if args.dry_run:
            continue

        if target_quant:
            if float(target_quant["quantity"] or 0.0) != target_qty:
                models.execute_kw(
                    args.db,
                    uid,
                    args.password,
                    "stock.quant",
                    "write",
                    [[target_quant["id"]], {"quantity": target_qty}],
                )
                writes += 1
        else:
            if target_qty != 0.0:
                models.execute_kw(
                    args.db,
                    uid,
                    args.password,
                    "stock.quant",
                    "create",
                    [[{"product_id": product_id, "location_id": lot_stock_location_id, "quantity": target_qty}]],
                )
                creates += 1

    print(f"Warehouse: {warehouse['code']} ({warehouse['name']}) location_id={lot_stock_location_id}")
    print(f"Woo storable products processed: {len(products)}")
    print(f"Multipack templates detected: {multipack_templates}")
    print(f"Quant writes: {writes}, creates: {creates}, negative-overflow guarded: {skipped_negative}")
    if args.dry_run:
        print("Dry run: no data written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
