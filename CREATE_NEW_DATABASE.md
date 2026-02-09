# Skapa ny ren Odoo-databas

## Steg 1: Gå till Database Manager
Öppna: https://snushallen.cloud/web/database/manager

## Steg 2: Skapa ny databas
- **Database Name**: `odoo_production`
- **Email**: `mikael@snushallen.se`
- **Password**: Välj ett starkt lösenord (t.ex. samma som API-nyckeln)
- **Language**: Swedish / Svenska
- **Country**: Sweden
- **Demo data**: Nej/No

## Steg 3: Uppdatera MCP-konfigurationen
Efter att databasen skapats, uppdatera `.vscode/mcp.json`:

```json
{
  "mcp-server-odoo": {
    "command": "npx",
    "args": ["-y", "mcp-server-odoo"],
    "env": {
      "ODOO_URL": "https://snushallen.cloud",
      "ODOO_DATABASE": "odoo_production",  // <-- Ändra här
      "ODOO_USER": "mikael@snushallen.se",
      "ODOO_API_KEY": "din-api-nyckel-här",
      "ODOO_YOLO": "read"
    }
  }
}
```

## Steg 4: Installera moduler i rätt ordning
1. **Stock/Inventory** (krävs för WMS)
2. **Prima WMS** (din custom modul)
3. **OCA WMS-moduler** (efter container restart)

## Fördelar med denna metod:
✅ Helt ren databas utan korrupt data
✅ Ingen risk för kvarvarande konflikter
✅ Odoo skapar rätt default warehouse automatiskt
✅ Tar bara några minuter
