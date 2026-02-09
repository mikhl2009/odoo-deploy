{
    "name": "Prima WMS Extension",
    "version": "18.0.1.0.0",
    "category": "Warehouse",
    "summary": "WMS-anpassningar för Prima Nordic Solution",
    "description": """
        Utökningar för lagerhantering:
        - Extra produktfält (leverantörens artikelnr, hyllplats)
        - Min-lager och beställningspunkt
        - Multi-store WooCommerce-koppling
    """,
    "author": "Prima Nordic Solution",
    "website": "https://primasolution.se",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "product",
        "sale_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
