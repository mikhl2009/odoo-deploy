#!/bin/bash
# =============================================================
# setup-submodules.sh — Lägg till alla OCA-moduler som submodules
# Kör detta EN gång i repots rot
# =============================================================

echo "🔧 Lägger till OCA-moduler som git submodules..."

# === MÅSTE HA ===
echo "📦 WMS (Shopfloor, scanner)..."
git submodule add -b 18.0 https://github.com/OCA/wms.git custom_addons/wms

echo "📦 Barcode scanning..."
git submodule add -b 18.0 https://github.com/OCA/stock-logistics-barcode.git custom_addons/stock-logistics-barcode

echo "📦 Lagerplatser, zoner..."
git submodule add -b 18.0 https://github.com/OCA/stock-logistics-warehouse.git custom_addons/stock-logistics-warehouse

echo "📦 Lager-arbetsflöden..."
git submodule add -b 18.0 https://github.com/OCA/stock-logistics-workflow.git custom_addons/stock-logistics-workflow

echo "📦 Produktattribut (PIM)..."
git submodule add -b 18.0 https://github.com/OCA/product-attribute.git custom_addons/product-attribute

echo "📦 Fraktbolag-kopplingar..."
git submodule add -b 18.0 https://github.com/OCA/delivery-carrier.git custom_addons/delivery-carrier

echo "📦 Returhantering (RMA)..."
git submodule add -b 18.0 https://github.com/OCA/rma.git custom_addons/rma

echo "📦 Helpdesk / Kundservice..."
git submodule add -b 18.0 https://github.com/OCA/helpdesk.git custom_addons/helpdesk

# === BRA ATT HA ===
echo "📦 Server tools (auto-update, etc.)..."
git submodule add -b 18.0 https://github.com/OCA/server-tools.git custom_addons/server-tools

echo "📦 Queue (bakgrundsjobb)..."
git submodule add -b 18.0 https://github.com/OCA/queue.git custom_addons/queue

echo "📦 Web UI förbättringar..."
git submodule add -b 18.0 https://github.com/OCA/web.git custom_addons/web

echo "📦 Produktvarianter..."
git submodule add -b 18.0 https://github.com/OCA/product-variant.git custom_addons/product-variant

echo "📦 Finansrapporter..."
git submodule add -b 18.0 https://github.com/OCA/account-financial-reporting.git custom_addons/account-financial-reporting

echo "📦 Utskriftshantering..."
git submodule add -b 18.0 https://github.com/OCA/report-print-send.git custom_addons/report-print-send

# === WOOCOMMERCE ===
echo "📦 WooCommerce Sync..."
git submodule add https://github.com/roboes/odoo-woocommerce-sync.git custom_addons/odoo-woocommerce-sync

echo ""
echo "✅ Alla submodules tillagda!"
echo ""
echo "Kör nu:"
echo "  git add ."
echo "  git commit -m 'Add OCA submodules'"
echo "  git push origin main"
