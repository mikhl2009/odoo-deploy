# Intercompany Setup (Odoo 18 Community)

This repository now includes OCA `multi-company` for Community intercompany flows.

## What was added

- Submodule: `custom_addons/multi-company` (branch `18.0`)
- Install script modules in `install_all_departments.py`:
  - `account_invoice_inter_company`
  - `purchase_sale_inter_company`
  - `purchase_sale_stock_inter_company`

## Install the modules

1. Update module list in Odoo Apps.
2. Install these modules (order shown):
   - `account_invoice_inter_company`
   - `purchase_sale_inter_company`
   - `purchase_sale_stock_inter_company`

You can also use:

```bash
python install_all_departments.py --url https://YOUR_ODOO_URL --db YOUR_DB
```

## Company configuration (for your scenario)

Scenario:
- `Snushallen i Norden AB` = wholesaler/source company
- `Vapehandel.se` = reseller/destination company

Required setup:

1. Create at least one warehouse per company.
2. In `Vapehandel.se`, create supplier contact `Snushallen i Norden AB` (company contact).
3. Go to `Settings -> General Settings -> Companies / Inter Company OCA features`.
4. For each company, configure:
   - `Sale from purchase` = enabled
   - `Intercompany Sale User` = set
   - `Sale Orders Auto Validation` = optional (enable for full automation)
   - `Warehouse For Sale Orders` = set (company warehouse)
   - `Sync picking` = optional (enable if you want receipt/delivery sync)
   - `Block PO manual picking validation` = optional

## Expected flow

1. In `Vapehandel.se`, create PO to supplier `Snushallen i Norden AB`.
2. Confirm PO.
3. Odoo auto-creates SO in `Snushallen i Norden AB`.
4. If auto validation is enabled, SO is confirmed automatically.
5. Validate delivery in Snushallen.
6. Receipt in Vapehandel can be synchronized when `Sync picking` is enabled.
