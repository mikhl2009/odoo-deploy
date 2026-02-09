# 🛒 WooCommerce Integration Setup

## Översikt
Kopplar din Odoo 18-instans till WooCommerce för att synkronisera:
- ✅ Produkter (inklusive varianter)
- ✅ Lagersaldon
- ✅ Kunder
- ✅ Ordrar
- ✅ Produktbilder

## Steg 1: Installera queue_job modul

Queue Job krävs för att hantera bakgrundssynkronisering.

```bash
# Uppdatera och rebuilda för att få Python-dependencies
git add Dockerfile
git commit -m "Add WooCommerce Python dependencies"
git push origin main
```

Sedan i Odoo UI:
1. Gå till **Apps** → Uppdatera **⋮** → **Update Apps List**
2. Sök "**queue_job**" (från OCA server-tools)
3. Klicka **Install**

## Steg 2: Installera WooCommerce Sync

1. I Odoo Apps, sök "**woocommerce**"
2. Hitta **Odoo-WooCommerce Sync**
3. Klicka **Install**

## Steg 3: Skapa WooCommerce API-nycklar

I din WordPress/WooCommerce admin:

1. Gå till **WooCommerce → Settings → Advanced → REST API**
2. Klicka **Add key**
3. Konfigurera:
   - **Description**: Odoo Integration
   - **User**: Välj admin-användare
   - **Permissions**: **Read/Write**
4. Klicka **Generate API key**
5. **SPARA** Consumer key och Consumer secret (visas bara EN gång!)

## Steg 4: Konfigurera anslutning i Odoo

1. Gå till **Settings → Technical → WooCommerce → WooCommerce Websites**
2. Klicka **Create**
3. Fyll i:
   - **Name**: Din butiks namn
   - **URL**: `https://dinbutik.se` (utan /wp-json)
   - **Consumer Key**: Från steg 3
   - **Consumer Secret**: Från steg 3
   - **Version**: `wc/v3`
4. Testa anslutningen: Klicka **Test Connection**
5. Spara

## Steg 5: Konfigurera synkronisering

I WooCommerce Website-inställningarna:

### Produktsynkronisering
- **Sync Direction**: 
  - `WooCommerce to Odoo` - Importera produkter från WooCommerce
  - `Both Ways` - Tvåvägssynk (rekommenderat)
- **Sync Images**: ✅ Aktivera för produktbilder
- **Default Stock Location**: Välj ditt huvudlager

### Kund- och ordersynkronisering
- **Sync Customers**: ✅ Aktivera
- **Sync Orders**: ✅ Aktivera
- **Default Warehouse**: Välj lager för WooCommerce-ordrar

### Automatisk synkronisering
- **Enable Cron**: ✅ Aktivera schemalagd synkronisering
- **Cron Interval**: Välj frekvens (t.ex. var 15:e minut)

## Steg 6: Första synkroniseringen

1. I WooCommerce Website → Klicka **Sync Now**
2. Välj vad som ska synkas:
   - ✅ Products
   - ✅ Stock
   - ✅ Customers
   - ✅ Orders
3. Klicka **Start Sync**

Synkroniseringen körs i bakgrunden via Queue Jobs.

## Övervaka synkronisering

**Queue Jobs:**
- Gå till **Settings → Technical → Queue Jobs**
- Se status på pågående och slutförda jobb
- Vid fel: Klicka på jobbet för att se felmeddelande

## Fältmappning

### Prima WMS → WooCommerce
| Odoo-fält | WooCommerce-fält |
|-----------|------------------|
| `woo_product_id` | Product ID |
| `default_code` (SKU) | SKU |
| `name` | Product Name |
| `list_price` | Regular Price |
| `qty_available` | Stock Quantity |
| `description_sale` | Short Description |

### WooCommerce → Odoo
- **WooCommerce Product ID** sparas i `woo_product_id` (Prima WMS-fält)
- **WooCommerce Order ID** sparas på Sale Order
- **Customer email** används för att matcha/skapa kontakter

## Troubleshooting

### Problem: Modulen syns inte i Apps
**Lösning**: 
1. Uppdatera Apps List: **Apps → ⋮ → Update Apps List**
2. Om fortfarande inte synlig, kontrollera att rebuilden gick igenom

### Problem: "Module queue_job not found"
**Lösning**: 
Installera queue_job först från OCA server-tools modulen.

### Problem: "Authentication failed"
**Lösning**: 
1. Verifiera Consumer Key/Secret
2. Kontrollera att WooCommerce REST API är aktiverat
3. Testa manuellt: `https://dinbutik.se/wp-json/wc/v3/products`

### Problem: Produkter synkas inte
**Lösning**:
1. Kontrollera att produkter har SKU i WooCommerce
2. Verifiera att "Manage Stock" är aktiverat för produkter
3. Kolla Queue Jobs för felmeddelanden

## Bästa praxis

✅ **SKU är obligatoriskt** - Varje produkt måste ha unikt SKU
✅ **Testa först** - Använd testdata innan produktions-synk
✅ **Backup** - Ta backup av både Odoo och WooCommerce innan stor synk
✅ **Övervakning** - Kolla Queue Jobs regelbundet för fel
✅ **Lagerhantering** - Konfigurera tydliga lagerplatser i Prima WMS

## Nästa steg

Efter framgångsrik integration:
1. Konfigurera Prima WMS-fält (`shelf_location`, `min_stock_qty`, `reorder_point`)
2. Installera OCA WMS-moduler för avancerad lagerstyrning
3. Konfigurera automatisk påfyllnad (reorder rules)
4. Sätt upp barcode-scanning för lager

## Support & Dokumentation

- **WooCommerce Sync GitHub**: https://github.com/roboes/odoo-woocommerce-sync
- **Queue Job Docs**: https://github.com/OCA/queue/tree/18.0/queue_job
- **Odoo WMS Docs**: https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory.html
