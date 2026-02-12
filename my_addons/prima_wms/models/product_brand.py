from odoo import models, fields


class PrimaBrand(models.Model):
    _name = "prima.brand"
    _description = "Varumärke"
    _order = "name"

    name = fields.Char(string="Namn", required=True, index=True)
    code = fields.Char(string="Kod", help="Kort kod för varumärket")
    active = fields.Boolean(default=True)
    supplier_id = fields.Many2one(
        "res.partner",
        string="Standardleverantör",
        domain=[("supplier_rank", ">", 0)],
    )
    product_count = fields.Integer(
        string="Antal produkter",
        compute="_compute_product_count",
    )
    note = fields.Text(string="Anteckning")

    def _compute_product_count(self):
        for brand in self:
            brand.product_count = self.env["product.template"].search_count(
                [("prima_brand_id", "=", brand.id)]
            )

    _sql_constraints = [
        ("name_unique", "UNIQUE(name)", "Varumärket finns redan!"),
    ]
