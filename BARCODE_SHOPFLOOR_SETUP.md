# Barcode Reception Setup (Odoo 18 Community)

This setup replaces the Enterprise barcode app with OCA Shopfloor modules.

## Modules

Install these modules:

1. `component`
2. `endpoint_route_handler`
3. `base_rest`
4. `shopfloor_base`
5. `shopfloor_mobile_base`
6. `shopfloor`
7. `shopfloor_reception`
8. `shopfloor_mobile`
9. `shopfloor_reception_mobile`

`install_all_departments.py` now includes them.

## Scanner requirements

- Use scanner mode: `HID keyboard`
- Suffix: `Enter` (CR/LF)
- Keyboard layout on device/browser must match scanner layout

## Warehouse setup

1. Enable multi-step receipts if needed for your process.
2. Ensure products have valid `barcode` (EAN/UPC).
3. In operation type for receipts, ensure barcode usage is enabled.
4. Give warehouse users access to Shopfloor user groups.

## Receiving flow for operators

1. Open Shopfloor reception screen on handheld/mobile.
2. Scan receipt/picking reference (or select from list).
3. Scan product EAN.
4. Enter/confirm quantity.
5. Repeat for all lines, then validate receipt.

## How to verify WooCommerce stock sync

1. Complete receipt validation in Odoo.
2. Check product fields:
   - `woocommerce_stock_last_sync`
   - stock quantity on the product in the correct company
3. If scheduled sync is enabled in Woo connector, wait one cycle.
4. Otherwise run manual sync from WooCommerce connector.
