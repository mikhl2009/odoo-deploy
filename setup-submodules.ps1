# =============================================================
# setup-submodules.ps1 — Lägg till alla OCA-moduler som submodules
# Kör detta EN gång i repots rot (PowerShell)
# =============================================================

Write-Host "🔧 Lägger till OCA-moduler som git submodules..." -ForegroundColor Cyan

# === MÅSTE HA ===
Write-Host "📦 WMS (Shopfloor, scanner)..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/wms.git custom_addons/wms

Write-Host "📦 Barcode scanning..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/stock-logistics-barcode.git custom_addons/stock-logistics-barcode

Write-Host "📦 Lagerplatser, zoner..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/stock-logistics-warehouse.git custom_addons/stock-logistics-warehouse

Write-Host "📦 Lager-arbetsflöden..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/stock-logistics-workflow.git custom_addons/stock-logistics-workflow

Write-Host "📦 Produktattribut (PIM)..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/product-attribute.git custom_addons/product-attribute

Write-Host "📦 Fraktbolag-kopplingar..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/delivery-carrier.git custom_addons/delivery-carrier

Write-Host "📦 Returhantering (RMA)..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/rma.git custom_addons/rma

Write-Host "📦 Helpdesk / Kundservice..." -ForegroundColor Green
git submodule add -b 18.0 https://github.com/OCA/helpdesk.git custom_addons/helpdesk

# === BRA ATT HA ===
Write-Host "📦 Server tools..." -ForegroundColor Yellow
git submodule add -b 18.0 https://github.com/OCA/server-tools.git custom_addons/server-tools

Write-Host "📦 Queue (bakgrundsjobb)..." -ForegroundColor Yellow
git submodule add -b 18.0 https://github.com/OCA/queue.git custom_addons/queue

Write-Host "📦 Web UI..." -ForegroundColor Yellow
git submodule add -b 18.0 https://github.com/OCA/web.git custom_addons/web

Write-Host "📦 Produktvarianter..." -ForegroundColor Yellow
git submodule add -b 18.0 https://github.com/OCA/product-variant.git custom_addons/product-variant

Write-Host "📦 Finansrapporter..." -ForegroundColor Yellow
git submodule add -b 18.0 https://github.com/OCA/account-financial-reporting.git custom_addons/account-financial-reporting

Write-Host "📦 Utskriftshantering..." -ForegroundColor Yellow
git submodule add -b 18.0 https://github.com/OCA/report-print-send.git custom_addons/report-print-send

# === WOOCOMMERCE ===
Write-Host "📦 WooCommerce Sync..." -ForegroundColor Magenta
git submodule add https://github.com/roboes/odoo-woocommerce-sync.git custom_addons/odoo-woocommerce-sync

Write-Host ""
Write-Host "✅ Alla submodules tillagda!" -ForegroundColor Green
Write-Host ""
Write-Host "Kör nu:" -ForegroundColor Cyan
Write-Host "  git add ."
Write-Host "  git commit -m 'Add OCA submodules'"
Write-Host "  git push origin main"
