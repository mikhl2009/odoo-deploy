/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class PrimaWmsDashboard extends Component {
    static template = "prima_wms.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.rpc = useService("rpc");

        this.state = useState({
            data: {},
            loading: true,
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            const result = await this.rpc("/prima_wms/dashboard_data", {});
            this.state.data = result;
        } catch (e) {
            console.error("Dashboard data error:", e);
        }
        this.state.loading = false;
    }

    formatNumber(num) {
        if (!num) return "0";
        return new Intl.NumberFormat("sv-SE").format(Math.round(num));
    }

    formatCurrency(num) {
        if (!num) return "0 kr";
        return new Intl.NumberFormat("sv-SE").format(Math.round(num)) + " kr";
    }

    // --- Navigation actions ---
    openProducts() {
        this.action.doAction("prima_wms.action_prima_product_list");
    }

    openLowStock() {
        this.action.doAction("prima_wms.action_prima_low_stock");
    }

    openPurchaseOrders() {
        this.action.doAction("prima_wms.action_prima_purchase_orders");
    }

    openNewProduct() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Ny produkt",
            res_model: "product.template",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openNewPO() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Ny inköpsorder",
            res_model: "purchase.order",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    openReceive() {
        this.action.doAction("prima_wms.action_prima_incoming_pickings");
    }

    openBrands() {
        this.action.doAction("prima_wms.action_prima_brand_list");
    }

    openSuppliers() {
        this.action.doAction("prima_wms.action_prima_suppliers");
    }

    openStocktake() {
        this.action.doAction("prima_wms.action_prima_stocktake");
    }

    openWaste() {
        this.action.doAction("prima_wms.action_prima_waste_wizard");
    }
}

registry.category("actions").add("prima_wms_dashboard", PrimaWmsDashboard);
