# Odoo 18 CE — Prima Nordic Solution

Komplett ERP-system med WMS, PIM, WooCommerce-sync, frakt, kundservice och returer.

## Stack
- **Odoo 18 Community Edition** (LGPL-3.0)
- **PostgreSQL 16**
- **Docker** → deployat via Coolify
- **OCA-moduler** för WMS, barcode, RMA, helpdesk

## Snabbstart (lokal utveckling)

```bash
docker compose -f docker-compose.yaml up -d
# Öppna http://localhost:8069
```

## Deploy till Coolify

Repot är kopplat till Coolify via GitHub. Push till `main` → auto-deploy.

## Struktur

```
├── Dockerfile              # Bygger Odoo + alla addons
├── docker-compose.yaml     # Odoo + PostgreSQL
├── config/odoo.conf        # Odoo-konfiguration
├── custom_addons/          # OCA community-moduler (git submodules)
│   ├── wms/
│   ├── stock-logistics-barcode/
│   ├── rma/
│   └── ...
└── my_addons/              # Egna moduler
    └── prima_wms/
```

## OCA-moduler (submodules)

```bash
git submodule update --init --recursive
```

## Miljövariabler (Coolify)

| Variabel | Beskrivning |
|----------|-------------|
| POSTGRES_USER | Databas-användare |
| POSTGRES_PASSWORD | Databas-lösenord |
| POSTGRES_DB | Databasnamn |

## Websocket in production

If you run `workers > 0` in Odoo, your reverse proxy must route `/websocket` to the evented port `8072`.
If `/websocket` is routed to `8069`, you will get:
`RuntimeError: Couldn't bind the websocket. Is the connection opened on the evented port (8072)?`

This repository currently defaults to `workers = 0` in `config/odoo.conf` for stable operation without extra proxy routing rules.

## Intercompany (Community)

For intercompany PO/SO automation in Odoo Community, see:

- `INTERCOMPANY_SETUP.md`

## Barcode Reception (Community)

For scanner-based receiving without Enterprise barcode app, see:

- `BARCODE_SHOPFLOOR_SETUP.md`
