import json
from datetime import timedelta

from odoo import http, fields
from odoo.http import request


class PrimaDashboard(http.Controller):

    @http.route("/prima_wms/dashboard_data", type="json", auth="user")
    def get_dashboard_data(self):
        """Returnerar KPI-data för WMS-dashboarden"""
        today = fields.Date.today()
        week_start = today - timedelta(days=today.weekday())

        Product = request.env["product.template"]
        PO = request.env["purchase.order"]
        Brand = request.env["prima.brand"]
        Partner = request.env["res.partner"]
        Log = request.env["prima.inventory.log"]

        # --- Produkter ---
        product_count = Product.search_count(
            [("detailed_type", "in", ["product", "consu"])]
        )

        # --- Lagersaldo totalt ---
        products = Product.search([("detailed_type", "in", ["product", "consu"])])
        total_stock = sum(products.mapped("qty_available"))

        # --- På väg ---
        total_incoming = sum(products.mapped("incoming_qty_prima"))

        # --- Lagervärde (FIFO) ---
        layers = request.env["stock.valuation.layer"].search([
            ("remaining_qty", ">", 0),
        ])
        total_value = sum(layers.mapped("remaining_value"))

        # --- Lågt lagersaldo ---
        low_stock_count = Product.search_count([("is_low_stock", "=", True)])

        # --- Försäljning denna vecka ---
        sale_logs = Log.search([
            ("move_type", "=", "sale"),
            ("create_date", ">=", fields.Datetime.to_string(
                fields.Datetime.now().replace(
                    hour=0, minute=0, second=0
                ) - timedelta(days=fields.Date.today().weekday())
            )),
        ])
        sales_this_week = abs(sum(sale_logs.mapped("quantity")))

        # --- Försäljning idag ---
        today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        today_logs = Log.search([
            ("move_type", "=", "sale"),
            ("create_date", ">=", fields.Datetime.to_string(today_start)),
        ])
        sales_today = abs(sum(today_logs.mapped("quantity")))

        # --- Ordrar denna vecka (unika referenser) ---
        week_sale_logs = Log.search([
            ("move_type", "=", "sale"),
            ("create_date", ">=", fields.Datetime.to_string(
                fields.Datetime.now().replace(
                    hour=0, minute=0, second=0
                ) - timedelta(days=fields.Date.today().weekday())
            )),
            ("reference", "!=", False),
        ])
        unique_orders_week = len(set(week_sale_logs.mapped("reference")))

        today_sale_logs = Log.search([
            ("move_type", "=", "sale"),
            ("create_date", ">=", fields.Datetime.to_string(today_start)),
            ("reference", "!=", False),
        ])
        unique_orders_today = len(set(today_sale_logs.mapped("reference")))

        # --- Status ---
        brand_count = Brand.search_count([])
        supplier_count = Partner.search_count([("supplier_rank", ">", 0)])
        open_po_count = PO.search_count([("state", "=", "purchase")])

        return {
            "product_count": product_count,
            "total_stock": int(total_stock),
            "total_incoming": int(total_incoming),
            "total_value": round(total_value, 0),
            "low_stock_count": low_stock_count,
            "sales_this_week": int(sales_this_week),
            "sales_today": int(sales_today),
            "unique_orders_week": unique_orders_week,
            "unique_orders_today": unique_orders_today,
            "brand_count": brand_count,
            "supplier_count": supplier_count,
            "open_po_count": open_po_count,
        }
