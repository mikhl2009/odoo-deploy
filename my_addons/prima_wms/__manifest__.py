{
    "name": "Prima WMS - Warehouse Management",
    "version": "18.0.2.0.0",
    "category": "Warehouse",
    "summary": "Komplett WMS för Snushallen — Dashboard, Inköp, Lager, Inventering, Rapporter",
    "description": """
        Fullständigt Warehouse Management System anpassat för Snushallen/Prima Nordic Solution.

        Funktioner:
        - Dashboard med KPI:er (produkter, lagersaldo, lagervärde, lågt saldo, försäljning)
        - Varumärkeshantering
        - Utökad produkthantering (SMD-nr, hyllplats, min-lager, varumärke)
        - Inköpsorderhantering med inleveransflöde
        - Inventering med diff-rapportering
        - Svinnregistrering
        - Lagerhistorik / audit log
        - Rapporter: Försäljning, COGS (FIFO), Svinn, Inventeringsdiff
        - WooCommerce webhook-integration
    """,
    "author": "Prima Nordic Solution",
    "website": "https://primasolution.se",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "stock_account",
        "product",
        "purchase",
        "sale_management",
    ],
    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/sequence_data.xml",
        "data/cron_data.xml",
        # Wizards
        "wizard/stocktake_wizard_views.xml",
        "wizard/waste_wizard_views.xml",
        # Views
        "views/dashboard_views.xml",
        "views/product_views.xml",
        "views/brand_views.xml",
        "views/purchase_views.xml",
        "views/inventory_log_views.xml",
        "views/report_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "prima_wms/static/src/js/dashboard.js",
            "prima_wms/static/src/xml/dashboard_template.xml",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
