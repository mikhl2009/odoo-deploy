from odoo import models, fields, api


class PrimaWasteLog(models.Model):
    """Svinnregistrering — loggar kasserade produkter"""
    _name = "prima.waste.log"
    _description = "Svinnlogg"
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
    quantity = fields.Float(
        string="Antal",
        required=True,
    )
    reason = fields.Selection(
        [
            ("expired", "Utgånget datum"),
            ("damaged", "Skadat"),
            ("defective", "Defekt/felaktigt"),
            ("other", "Övrigt"),
        ],
        string="Orsak",
        required=True,
        default="expired",
    )
    note = fields.Text(string="Notering")
    user_id = fields.Many2one(
        "res.users",
        string="Registrerad av",
        default=lambda self: self.env.user,
    )
    scrap_id = fields.Many2one(
        "stock.scrap",
        string="Kassering",
    )
    cost = fields.Float(
        string="Kostnad",
        compute="_compute_cost",
        store=True,
        digits="Product Price",
    )

    @api.depends("quantity", "product_id")
    def _compute_cost(self):
        for rec in self:
            rec.cost = rec.quantity * (rec.product_id.standard_price or 0.0)

    def action_create_scrap(self):
        """Skapa en Odoo-kassering (stock.scrap) baserat på svinnraden"""
        self.ensure_one()
        scrap = self.env["stock.scrap"].create({
            "product_id": self.product_id.id,
            "scrap_qty": self.quantity,
            "origin": f"Svinn: {self.reason}",
        })
        scrap.action_validate()
        self.scrap_id = scrap.id

        # Logga i historik
        self.env["prima.inventory.log"].log_movement(
            product=self.product_id,
            move_type="waste",
            quantity=-abs(self.quantity),
            reference=scrap.name,
            note=f"Svinn: {dict(self._fields['reason'].selection).get(self.reason)} — {self.note or ''}",
        )
        return True
