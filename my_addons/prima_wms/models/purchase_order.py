from odoo import models, fields, api


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    prima_notes = fields.Text(string="WMS-notering")
    total_ordered_qty = fields.Float(
        string="Beställt (antal)",
        compute="_compute_qty_totals",
        store=True,
    )
    total_received_qty = fields.Float(
        string="Levererat (antal)",
        compute="_compute_qty_totals",
        store=True,
    )
    total_remaining_qty = fields.Float(
        string="Återstår (antal)",
        compute="_compute_qty_totals",
        store=True,
    )

    @api.depends(
        "order_line.product_qty",
        "order_line.qty_received",
    )
    def _compute_qty_totals(self):
        for order in self:
            order.total_ordered_qty = sum(order.order_line.mapped("product_qty"))
            order.total_received_qty = sum(order.order_line.mapped("qty_received"))
            order.total_remaining_qty = (
                order.total_ordered_qty - order.total_received_qty
            )

    def action_create_inbound_picking(self):
        """Snabbknapp: Skapa inleveransplockning"""
        self.ensure_one()
        pickings = self.picking_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
            and p.picking_type_id.code == "incoming"
        )
        if pickings:
            return {
                "type": "ir.actions.act_window",
                "name": "Inleverans",
                "res_model": "stock.picking",
                "res_id": pickings[0].id,
                "view_mode": "form",
            }
        return {"type": "ir.actions.act_window_close"}


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    prima_brand_id = fields.Many2one(
        related="product_id.product_tmpl_id.prima_brand_id",
        string="Varumärke",
        store=True,
    )
    remaining_qty = fields.Float(
        string="Återstår",
        compute="_compute_remaining_qty",
        store=True,
    )

    @api.depends("product_qty", "qty_received")
    def _compute_remaining_qty(self):
        for line in self:
            line.remaining_qty = line.product_qty - line.qty_received
