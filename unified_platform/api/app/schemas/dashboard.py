from __future__ import annotations

from pydantic import BaseModel


class DashboardKpiResponse(BaseModel):
    products_total: int
    variants_total: int
    suppliers_total: int
    purchase_orders_open: int
    inbound_shipments_active: int
    low_stock_alerts_open: int
    stock_value_fifo: float
    stock_value_wac: float
