from odoo import models, fields, api


class PrimaInventoryLog(models.Model):
    """Lagerhistorik — loggar alla lagerrörelser (motsvarar Historik-sidan i WMS)"""
    _name = "prima.inventory.log"
    _description = "Lagerrörelselogg"
    _order = "create_date desc"

    product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        required=True,
        index=True,
    )
    product_sku = fields.Char(
        string="Art.nr",
        related="product_id.default_code",
        store=True,
    )
    product_name = fields.Char(
        string="Produktnamn",
        related="product_id.name",
        store=True,
    )

    move_type = fields.Selection(
        [
            ("sale", "Försäljning"),
            ("purchase", "Inköp/Inleverans"),
            ("inventory", "Inventering"),
            ("waste", "Svinn"),
            ("adjustment", "Justering"),
            ("return", "Retur"),
            ("other", "Övrigt"),
        ],
        string="Typ",
        required=True,
        index=True,
    )

    quantity = fields.Float(
        string="Antal",
        help="Positivt = in, Negativt = ut",
    )
    reference = fields.Char(
        string="Referens",
        help="T.ex. WooCommerce order-ID, PO-nummer",
        index=True,
    )
    note = fields.Text(string="Notering")
    user_id = fields.Many2one(
        "res.users",
        string="Skapad av",
        default=lambda self: self.env.user,
    )

    # Kopplingar
    stock_move_id = fields.Many2one(
        "stock.move",
        string="Lagerrörelse",
    )
    picking_id = fields.Many2one(
        "stock.picking",
        string="Plockning",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Försäljningsorder",
    )
    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Inköpsorder",
    )

    @api.model
    def log_movement(self, product, move_type, quantity, reference="", note="",
                     stock_move=None, picking=None, sale_order=None, purchase_order=None):
        """Hjälpmetod för att logga en lagerrörelse"""
        return self.create({
            "product_id": product.id,
            "move_type": move_type,
            "quantity": quantity,
            "reference": reference,
            "note": note,
            "stock_move_id": stock_move.id if stock_move else False,
            "picking_id": picking.id if picking else False,
            "sale_order_id": sale_order.id if sale_order else False,
            "purchase_order_id": purchase_order.id if purchase_order else False,
        })


class StockMove(models.Model):
    """Utöka stock.move för att automatiskt logga till prima.inventory.log"""
    _inherit = "stock.move"

    def _action_done(self, cancel_backorder=False):
        """Override för att logga rörelser automatiskt"""
        res = super()._action_done(cancel_backorder=cancel_backorder)
        log_model = self.env["prima.inventory.log"]

        for move in res:
            if move.state != "done":
                continue

            # Bestäm typ
            picking = move.picking_id
            if picking and picking.picking_type_id.code == "outgoing":
                move_type = "sale"
                qty = -abs(move.quantity)
                ref = picking.origin or picking.name
                sale = picking.sale_id if hasattr(picking, "sale_id") else False
                log_model.log_movement(
                    product=move.product_id,
                    move_type=move_type,
                    quantity=qty,
                    reference=ref,
                    stock_move=move,
                    picking=picking,
                    sale_order=sale,
                )
            elif picking and picking.picking_type_id.code == "incoming":
                move_type = "purchase"
                qty = abs(move.quantity)
                ref = picking.origin or picking.name
                po = (
                    move.purchase_line_id.order_id
                    if move.purchase_line_id
                    else False
                )
                log_model.log_movement(
                    product=move.product_id,
                    move_type=move_type,
                    quantity=qty,
                    reference=ref,
                    stock_move=move,
                    picking=picking,
                    purchase_order=po,
                )
            elif picking and picking.picking_type_id.code == "internal":
                log_model.log_movement(
                    product=move.product_id,
                    move_type="other",
                    quantity=move.quantity,
                    reference=picking.name,
                    note="Intern förflyttning",
                    stock_move=move,
                    picking=picking,
                )

        return res
