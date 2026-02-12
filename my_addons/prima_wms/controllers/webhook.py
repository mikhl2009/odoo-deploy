import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PrimaWebhook(http.Controller):

    @http.route(
        "/api/webhooks/woocommerce/order",
        type="json",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def woocommerce_order_webhook(self):
        """
        Tar emot WooCommerce order-webhooks och loggar lagerrörelser.
        Matchar produkter via default_code (artikelnummer) eller woo_product_id.
        """
        try:
            data = request.get_json_data()
        except Exception:
            data = json.loads(request.httprequest.data.decode("utf-8"))

        if not data:
            _logger.warning("WMS Webhook: Tom request mottagen")
            return {"status": "error", "message": "No data"}

        order_id = data.get("id", "")
        order_number = data.get("number", str(order_id))
        status = data.get("status", "")
        line_items = data.get("line_items", [])

        _logger.info(
            "WMS Webhook: Order #%s, status=%s, %d rader",
            order_number, status, len(line_items),
        )

        # Bara hantera completed / processing ordrar
        if status not in ("processing", "completed"):
            return {"status": "ok", "message": f"Ignorerar status: {status}"}

        # Sök produkter med sudo för att webhook har auth=none
        env = request.env(su=True)
        Log = env["prima.inventory.log"]
        Product = env["product.product"]

        processed = 0
        for item in line_items:
            sku = item.get("sku", "")
            woo_pid = str(item.get("product_id", ""))
            qty = item.get("quantity", 0)
            name = item.get("name", "")

            # Försök matcha produkt
            product = False
            if sku:
                product = Product.search([("default_code", "=", sku)], limit=1)
            if not product and woo_pid:
                product = Product.search([
                    ("product_tmpl_id.woo_product_id", "=", woo_pid)
                ], limit=1)

            if product:
                Log.create({
                    "product_id": product.id,
                    "move_type": "sale",
                    "quantity": -abs(qty),
                    "reference": f"woocommerce_order / WH{order_number} / {item.get('id', '')}",
                    "note": f"WooCommerce order #{order_number}: {name}",
                })
                processed += 1
            else:
                _logger.warning(
                    "WMS Webhook: Produkt ej hittad — SKU=%s, WooID=%s, Namn=%s",
                    sku, woo_pid, name,
                )

        _logger.info("WMS Webhook: %d av %d rader processade", processed, len(line_items))
        return {
            "status": "ok",
            "processed": processed,
            "total_items": len(line_items),
        }
