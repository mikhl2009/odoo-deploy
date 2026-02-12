from odoo import models, fields, api


class WasteWizard(models.TransientModel):
    """Svinnregistrering — motsvarar 'Registrera Svinn' i PHP WMS"""
    _name = "prima.waste.wizard"
    _description = "Registrera Svinn"

    product_id = fields.Many2one(
        "product.product",
        string="Produkt",
        required=True,
        domain=[("type", "=", "product")],
    )
    quantity = fields.Float(string="Antal", required=True, default=1)
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

    def action_register_waste(self):
        """Registrera svinn och skapa kassering"""
        self.ensure_one()
        waste = self.env["prima.waste.log"].create({
            "product_id": self.product_id.id,
            "quantity": self.quantity,
            "reason": self.reason,
            "note": self.note,
        })
        waste.action_create_scrap()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Svinn registrerat",
                "message": f"{self.quantity} st {self.product_id.name} kasserat ({self.reason}).",
                "type": "warning",
                "sticky": False,
            },
        }
