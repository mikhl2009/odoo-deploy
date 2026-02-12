#!/usr/bin/env python3
"""Patch WooCommerce connector transaction handling for queue jobs.

This script makes the patch reproducible from the parent repository, so we
don't need to commit directly inside the upstream submodule.
"""

from pathlib import Path
import sys


TARGET_DEFAULT = "/mnt/extra-addons/odoo-woocommerce-sync/woocommerce_sync/models/connector.py"
WIDGET_FIELD_BAD = 'name="woocommerce_default_attributes" widget="html"'
WIDGET_FIELD_GOOD = 'name="woocommerce_default_attributes" widget="json_html"'
WIDGET_VIEW_PATHS = (
    Path("views/v16/product_template_form.xml"),
    Path("views/v18/product_template_form.xml"),
    Path("views/v19/product_template_form.xml"),
)

LOGGER_LINES = [
    """            _logger.exception(f'Error syncing WooCommerce product {woocommerce_product["name"]} (WooCommerce product ID: {woocommerce_product["id"]}): {error}')\n""",
    """            _logger.exception(f'Error syncing WooCommerce product: {woocommerce_product["name"]} (WooCommerce product ID: {woocommerce_product["id"]}): {error}')\n""",
    """            _logger.exception(f'Error syncing WooCommerce customer: {woocommerce_customer["first_name"]} {woocommerce_customer["last_name"]} (WooCommerce customer ID: {woocommerce_customer["id"]}): {error}')\n""",
    """            _logger.exception(f'Error syncing WooCommerce order {woocommerce_order["id"]}: {error}')\n""",
]

TAX_MISMATCH_BAD = """            _logger.info(f'Mismatch between Odoo and WooCommerce tax rate settings for inclusion of tax in price: {odoo_tax_rate.name}')\n"""
TAX_MISMATCH_GOOD = """            _logger.info(\n                f\"Mismatch between Odoo and WooCommerce tax price-inclusion settings. \"\n                f\"Company default price_include={odoo_price_include_tax}, incoming price_include={price_include_tax}, tax_rate={tax_rate}\"\n            )\n"""

TAX_EXCEPT_BAD = """            _logger.error(f'Failed to create or retrieve WooCommerce tax rate in Odoo: {odoo_tax_rate}%: {error}')\n"""
TAX_EXCEPT_GOOD = """            _logger.error(f'Failed to create or retrieve WooCommerce tax rate in Odoo: {tax_rate}%: {error}')\n"""

IMPORT_IO_LINE = "from io import BytesIO\n"
IMPORT_JSON_LINE = "import json\n"
IMPORT_LOGGING_LINE = "import logging\n"
IMPORT_RE_LINE = "import re\n"

BARCODE_HELPER_BLOCK = """
    @staticmethod
    def _barcode_normalize(value: Any) -> str | bool:
        if value in [None, False]:
            return False

        if isinstance(value, dict):
            for nested_value in value.values():
                barcode = WoocommerceSyncConnector._barcode_normalize(nested_value)
                if barcode:
                    return barcode
            return False

        if isinstance(value, (list, tuple, set)):
            for nested_value in value:
                barcode = WoocommerceSyncConnector._barcode_normalize(nested_value)
                if barcode:
                    return barcode
            return False

        if isinstance(value, float) and value.is_integer():
            value = int(value)

        barcode = str(value).strip().replace(' ', '')
        return barcode if barcode else False

    @api.model
    def woocommerce_extract_barcode(self: models.Model, woocommerce_record: dict[str, Any] | None) -> str | bool:
        if not isinstance(woocommerce_record, dict):
            return False

        # Direct keys that some WooCommerce barcode plugins expose.
        direct_keys = ['barcode', 'ean', 'ean13', 'gtin', 'gtin13', 'upc', 'global_unique_id']
        for key in direct_keys:
            barcode = self._barcode_normalize(woocommerce_record.get(key))
            if barcode:
                return barcode

        meta_entries = woocommerce_record.get('meta_data') or []
        if not isinstance(meta_entries, list):
            return False

        meta_map = {}
        for entry in meta_entries:
            if not isinstance(entry, dict):
                continue
            key = entry.get('key')
            if not key:
                continue
            meta_map[str(key).strip().lower()] = entry.get('value')

        meta_keys = [
            'ean',
            '_ean',
            'ean13',
            '_ean13',
            'gtin',
            '_gtin',
            'gtin13',
            '_gtin13',
            '_alg_wc_ean',
            '_alg_ean',
            '_wpm_gtin_code',
            'barcode',
            '_barcode',
            '_ywbc_barcode_display_value',
        ]
        for key in meta_keys:
            barcode = self._barcode_normalize(meta_map.get(key))
            if barcode:
                return barcode

        # Yoast SEO "global identifier values" format (stored as dict or JSON string).
        yoast_identifiers = (
            meta_map.get('wpseo_global_identifier_values')
            or meta_map.get('wpseo_variation_global_identifiers_values')
        )
        if isinstance(yoast_identifiers, str):
            try:
                yoast_identifiers = json.loads(yoast_identifiers)
            except ValueError:
                yoast_identifiers = {}

        if isinstance(yoast_identifiers, dict):
            for key in ['gtin13', 'gtin14', 'gtin12', 'gtin8', 'ean', 'upc', 'isbn', 'mpn']:
                barcode = self._barcode_normalize(yoast_identifiers.get(key))
                if barcode:
                    return barcode

        return False
"""

IMAGE_FUNC_MARKER = "\n    @api.model\n    def image_download_file_to_base64"

PRODUCT_SERVICE_BLOCK = """                'woocommerce_service': False,  # woocommerce_product.get('service', False), # Germanized field - https://vendidero.de/doc/woocommerce-germanized/products-rest-api\n            },\n        )\n"""
PRODUCT_BARCODE_BLOCK = PRODUCT_SERVICE_BLOCK + """
        barcode = self.woocommerce_extract_barcode(woocommerce_product)
        if barcode:
            product_values['barcode'] = barcode
"""

VARIATION_SERVICE_BLOCK = """                'woocommerce_service': False,  # product.get('service', False), # Germanized field - https://vendidero.de/doc/woocommerce-germanized/products-rest-api\n            },\n        )\n"""
VARIATION_BARCODE_BLOCK = VARIATION_SERVICE_BLOCK + """
        barcode = self.woocommerce_extract_barcode(woocommerce_variation)
        if barcode:
            product_variation_values['barcode'] = barcode
"""

PRODUCT_TYPE_MARKER = "            # Product type\n"
WOO_PRODUCT_ID_BLOCK = """            if 'woo_product_id' in self.env['product.template']._fields:
                product_values['woo_product_id'] = str(product_values['woocommerce_id'])

""" + PRODUCT_TYPE_MARKER

ORDER_LINE_MODELS_MARKER = """                # Odoo 'sale.order.line' model fields
                sale_order_line_fields = {
"""
ORDER_LINE_MODELS_BLOCK = """                # Normalize multi-pack order lines to 1-pack stock movement.
                normalized_product_for_stock = odoo_product_mapped
                pack_multiplier = 1.0
                if odoo_product_mapped and getattr(odoo_product_mapped, '_name', '') == 'product.product':
                    candidates = [
                        order_line_values.get('woocommerce_name') or '',
                        order_line_values.get('woocommerce_sku') or '',
                        odoo_product_mapped.display_name or '',
                        ' '.join(odoo_product_mapped.product_template_attribute_value_ids.mapped('name')),
                    ]
                    for candidate in candidates:
                        candidate_lower = str(candidate).lower()
                        match = re.search(r'(?:^|\\D)(\\d+)\\s*[- ]?pack(?:\\b|$)', candidate_lower)
                        if match:
                            pack_multiplier = float(match.group(1))
                            break
                    if pack_multiplier > 1:
                        odoo_base_variant = odoo_product_mapped.product_tmpl_id.product_variant_ids.filtered(
                            lambda variant: variant.active
                            and (
                                '1-pack' in ' '.join(variant.product_template_attribute_value_ids.mapped('name')).lower()
                                or '1 pack' in ' '.join(variant.product_template_attribute_value_ids.mapped('name')).lower()
                            )
                        )[:1]
                        if odoo_base_variant:
                            normalized_product_for_stock = odoo_base_variant

                normalized_qty = float(order_line_values['woocommerce_quantity'] or 0.0) * pack_multiplier

""" + ORDER_LINE_MODELS_MARKER

ORDER_LINE_PRODUCT_ID_OLD = """                    'product_id': odoo_product_mapped.id if odoo_product_mapped else odoo_product.product_variant_ids[:1].id,
"""
ORDER_LINE_PRODUCT_ID_NEW = """                    'product_id': normalized_product_for_stock.id if normalized_product_for_stock else odoo_product.product_variant_ids[:1].id,
"""

ORDER_LINE_QTY_OLD = """                    'product_uom_qty': order_line_values['woocommerce_quantity'],
"""
ORDER_LINE_QTY_NEW = """                    'product_uom_qty': normalized_qty,
"""

DESCRIPTION_SALE_PRODUCT_OLD = """                    'description_sale': product_values['woocommerce_description'],
"""
DESCRIPTION_SALE_PRODUCT_NEW = """                    'description_sale': False,
"""

DESCRIPTION_SALE_VARIATION_OLD = """                            'description_sale': product_variation_values['woocommerce_description'],
"""
DESCRIPTION_SALE_VARIATION_NEW = """                            'description_sale': False,
"""


def patch_widget_views(module_root: Path) -> int:
    patched = 0
    for rel_path in WIDGET_VIEW_PATHS:
        view_path = module_root / rel_path
        if not view_path.exists():
            print(f"Widget patch skipped (missing file): {view_path}")
            continue
        view_text = view_path.read_text(encoding="utf-8").replace("\r\n", "\n")
        new_view_text = view_text.replace(WIDGET_FIELD_BAD, WIDGET_FIELD_GOOD)
        if new_view_text != view_text:
            view_path.write_text(new_view_text, encoding="utf-8", newline="\n")
            patched += 1
    return patched


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(TARGET_DEFAULT)
    if not target.exists():
        print(f"Target file not found: {target}")
        return 1

    text = target.read_text(encoding="utf-8")
    # Normalize newlines so string-based patching works regardless of source OS.
    text = text.replace("\r\n", "\n")
    original = text

    # Rolling back inside queue_job_cron_jobrunner savepoints breaks transaction
    # state and can crash the job runner with InvalidSavepointSpecification.
    text = text.replace("            # Roll back changes\n            self.env.cr.rollback()\n", "")

    inserted = 0
    for line in LOGGER_LINES:
        with_raise = f"{line}            raise\n"
        if with_raise in text:
            continue
        if line in text:
            text = text.replace(line, with_raise, 1)
            inserted += 1

    # Fix UnboundLocalError in tax-rate helper (odoo_tax_rate used before assignment).
    if TAX_MISMATCH_BAD in text:
        text = text.replace(TAX_MISMATCH_BAD, TAX_MISMATCH_GOOD, 1)
    if TAX_EXCEPT_BAD in text:
        text = text.replace(TAX_EXCEPT_BAD, TAX_EXCEPT_GOOD, 1)

    # Barcode/EAN extraction support + Prima WMS Woo ID mapping.
    if IMPORT_JSON_LINE not in text and IMPORT_IO_LINE in text:
        text = text.replace(IMPORT_IO_LINE, IMPORT_IO_LINE + IMPORT_JSON_LINE, 1)
    if IMPORT_RE_LINE not in text and IMPORT_LOGGING_LINE in text:
        text = text.replace(IMPORT_LOGGING_LINE, IMPORT_LOGGING_LINE + IMPORT_RE_LINE, 1)

    if "def woocommerce_extract_barcode(" not in text and IMAGE_FUNC_MARKER in text:
        text = text.replace(IMAGE_FUNC_MARKER, "\n" + BARCODE_HELPER_BLOCK + IMAGE_FUNC_MARKER, 1)

    if "barcode = self.woocommerce_extract_barcode(woocommerce_product)" not in text and PRODUCT_SERVICE_BLOCK in text:
        text = text.replace(PRODUCT_SERVICE_BLOCK, PRODUCT_BARCODE_BLOCK, 1)

    if "barcode = self.woocommerce_extract_barcode(woocommerce_variation)" not in text and VARIATION_SERVICE_BLOCK in text:
        text = text.replace(VARIATION_SERVICE_BLOCK, VARIATION_BARCODE_BLOCK, 1)

    if "if 'woo_product_id' in self.env['product.template']._fields" not in text and PRODUCT_TYPE_MARKER in text:
        text = text.replace(PRODUCT_TYPE_MARKER, WOO_PRODUCT_ID_BLOCK, 1)

    if "normalized_product_for_stock = odoo_product_mapped" not in text and ORDER_LINE_MODELS_MARKER in text:
        text = text.replace(ORDER_LINE_MODELS_MARKER, ORDER_LINE_MODELS_BLOCK, 1)

    if ORDER_LINE_PRODUCT_ID_OLD in text and ORDER_LINE_PRODUCT_ID_NEW not in text:
        text = text.replace(ORDER_LINE_PRODUCT_ID_OLD, ORDER_LINE_PRODUCT_ID_NEW, 1)

    if ORDER_LINE_QTY_OLD in text and ORDER_LINE_QTY_NEW not in text:
        text = text.replace(ORDER_LINE_QTY_OLD, ORDER_LINE_QTY_NEW, 1)

    # Keep sale order line labels clean: no HTML from Woo descriptions.
    if DESCRIPTION_SALE_PRODUCT_OLD in text and DESCRIPTION_SALE_PRODUCT_NEW not in text:
        text = text.replace(DESCRIPTION_SALE_PRODUCT_OLD, DESCRIPTION_SALE_PRODUCT_NEW, 1)
    if DESCRIPTION_SALE_VARIATION_OLD in text and DESCRIPTION_SALE_VARIATION_NEW not in text:
        text = text.replace(DESCRIPTION_SALE_VARIATION_OLD, DESCRIPTION_SALE_VARIATION_NEW, 1)

    if "self.env.cr.rollback()" in text:
        print("Patch failed: rollback calls still present in connector.py")
        return 2

    widget_patched = patch_widget_views(target.parent.parent)

    if text == original and widget_patched == 0:
        print("Patch already applied or not needed.")
        return 0

    if text != original:
        target.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"Patch applied to {target} "
        f"(logger raise inserts: {inserted}, widget view patches: {widget_patched})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
