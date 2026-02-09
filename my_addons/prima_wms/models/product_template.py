from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Leverantörsinfo
    supplier_sku = fields.Char(
        string="Leverantörens artikelnr",
        help="Artikelnummer hos leverantören",
    )

    # Lagerplats
    shelf_location = fields.Char(
        string="Hyllplats",
        help="T.ex. A-03-02 (Gång A, Hylla 3, Plats 2)",
    )

    # Lagernivåer
    min_stock_qty = fields.Float(
        string="Min lagersaldo",
        default=5.0,
        help="Varning visas när lagret understiger detta",
    )
    reorder_point = fields.Float(
        string="Beställningspunkt",
        help="Automatisk beställning triggas vid denna nivå",
    )

    # WooCommerce-info
    woo_product_id = fields.Char(
        string="WooCommerce Produkt-ID",
        help="ID i WooCommerce för synkronisering",
    )
