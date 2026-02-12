from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # --- Identifiering ---
    supplier_sku = fields.Char(
        string="Leverantörens artikelnr",
        help="Artikelnummer hos leverantören (SMD nr)",
    )
    smd_nr = fields.Char(
        string="SMD nr",
        help="SMD-nummer från grossisten",
    )

    # --- Varumärke ---
    prima_brand_id = fields.Many2one(
        "prima.brand",
        string="Varumärke",
        index=True,
    )

    # --- Lagerplats ---
    shelf_location = fields.Char(
        string="Hyllplats",
        help="T.ex. A-03-02 (Gång A, Hylla 3, Plats 2)",
    )

    # --- Lagernivåer ---
    min_stock_qty = fields.Float(
        string="Minimum i lager",
        default=0.0,
        help="Varning visas när lagret understiger detta",
    )
    is_low_stock = fields.Boolean(
        string="Lågt lagersaldo",
        compute="_compute_is_low_stock",
        store=True,
        help="Sant om aktuellt saldo < minimum i lager",
    )

    # --- WooCommerce ---
    woo_product_id = fields.Char(
        string="WooCommerce Produkt-ID",
        help="ID i WooCommerce för synkronisering",
    )

    # --- Inköpspris (senaste FIFO) ---
    last_purchase_price = fields.Float(
        string="Senaste inköpspris",
        digits="Product Price",
        help="Senaste inköpspris från inleverans",
    )

    # --- Beräknat lagervärde ---
    stock_value_fifo = fields.Float(
        string="Lagervärde (FIFO)",
        compute="_compute_stock_value_fifo",
        digits="Product Price",
    )

    # --- På väg (inbound) ---
    incoming_qty_prima = fields.Float(
        string="På väg",
        compute="_compute_incoming_qty",
    )

    @api.depends("qty_available", "min_stock_qty")
    def _compute_is_low_stock(self):
        for product in self:
            product.is_low_stock = (
                product.min_stock_qty > 0
                and product.qty_available < product.min_stock_qty
            )

    def _compute_stock_value_fifo(self):
        for product in self:
            # Hämta summan av alla stock valuation layers
            layers = self.env["stock.valuation.layer"].search([
                ("product_id.product_tmpl_id", "=", product.id),
                ("remaining_qty", ">", 0),
            ])
            product.stock_value_fifo = sum(layers.mapped("remaining_value"))

    def _compute_incoming_qty(self):
        for product in self:
            # Hämta antal på väg från bekräftade PO-rader
            po_lines = self.env["purchase.order.line"].search([
                ("product_id.product_tmpl_id", "=", product.id),
                ("order_id.state", "in", ["purchase", "done"]),
            ])
            ordered = sum(po_lines.mapped("product_qty"))
            received = sum(po_lines.mapped("qty_received"))
            product.incoming_qty_prima = ordered - received

    def action_view_low_stock(self):
        """Öppna lista med produkter med lågt lagersaldo"""
        return {
            "type": "ir.actions.act_window",
            "name": "Lågt lagersaldo",
            "res_model": "product.template",
            "view_mode": "list,form",
            "domain": [("is_low_stock", "=", True)],
            "context": {"search_default_filter_low_stock": 1},
        }
