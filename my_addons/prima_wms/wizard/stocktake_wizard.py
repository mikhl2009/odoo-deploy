from odoo import models, fields, api


class StocktakeWizard(models.TransientModel):
    """Inventeringsguide — som Inventering-sidan i PHP WMS"""
    _name = "prima.stocktake.wizard"
    _description = "Inventering"

    note = fields.Char(string="Notering", help="T.ex. Inventering butik 2025-12-26")
    line_ids = fields.One2many(
        "prima.stocktake.wizard.line",
        "wizard_id",
        string="Produkter",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Ladda alla lagerförda produkter
        products = self.env["product.product"].search([
            ("type", "=", "product"),
            ("active", "=", True),
        ], order="default_code")

        lines = []
        for product in products:
            lines.append((0, 0, {
                "product_id": product.id,
                "current_qty": product.qty_available,
                "new_qty": product.qty_available,  # Default = ingen ändring
            }))
        res["line_ids"] = lines
        return res

    def action_save_stocktake(self):
        """Spara inventering — justerar lagersaldo och loggar diff"""
        self.ensure_one()
        Log = self.env["prima.inventory.log"]
        StockQuant = self.env["stock.quant"]

        location = self.env.ref("stock.stock_location_stock", raise_if_not_found=False)
        if not location:
            location = self.env["stock.location"].search(
                [("usage", "=", "internal")], limit=1
            )

        adjusted = 0
        for line in self.line_ids:
            diff = line.new_qty - line.current_qty
            if diff == 0:
                continue

            # Justera via stock.quant
            quant = StockQuant.search([
                ("product_id", "=", line.product_id.id),
                ("location_id", "=", location.id),
            ], limit=1)

            if quant:
                quant.sudo().with_context(inventory_mode=True).write({
                    "inventory_quantity": line.new_qty,
                })
                quant.sudo().action_apply_inventory()
            else:
                # Skapa quant om det inte finns
                StockQuant.sudo().with_context(inventory_mode=True).create({
                    "product_id": line.product_id.id,
                    "location_id": location.id,
                    "inventory_quantity": line.new_qty,
                })

            # Logga i historik
            Log.log_movement(
                product=line.product_id,
                move_type="inventory",
                quantity=diff,
                reference=f"Inventering: {self.note or fields.Date.today()}",
                note=f"Före: {line.current_qty}, Efter: {line.new_qty}, Diff: {diff:+.0f}",
            )
            adjusted += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Inventering sparad",
                "message": f"{adjusted} produkter justerade.",
                "type": "success",
                "sticky": False,
            },
        }


class StocktakeWizardLine(models.TransientModel):
    _name = "prima.stocktake.wizard.line"
    _description = "Inventeringsrad"

    wizard_id = fields.Many2one("prima.stocktake.wizard", required=True)
    product_id = fields.Many2one("product.product", string="Produkt", required=True)
    product_sku = fields.Char(
        string="Art.nr",
        related="product_id.default_code",
    )
    product_name = fields.Char(
        string="Namn",
        related="product_id.name",
    )
    brand_name = fields.Char(
        string="Varumärke",
        related="product_id.product_tmpl_id.prima_brand_id.name",
    )
    current_qty = fields.Float(string="Nuvarande saldo")
    new_qty = fields.Float(string="Inventerat (nytt saldo)")
    diff = fields.Float(
        string="Diff",
        compute="_compute_diff",
    )

    @api.depends("current_qty", "new_qty")
    def _compute_diff(self):
        for line in self:
            line.diff = line.new_qty - line.current_qty
