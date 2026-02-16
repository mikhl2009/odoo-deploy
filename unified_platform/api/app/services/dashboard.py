from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.inventory import InvInboundShipment, InvStockAlert, InvValuationLayer
from app.models.mdm import MdmPartner
from app.models.pim import PimProduct, PimProductVariant
from app.models.procurement import ProcPurchaseOrder
from app.schemas.dashboard import DashboardKpiResponse


def scalar_int(db: Session, stmt: Select) -> int:
    value = db.scalar(stmt)
    return int(value or 0)


def scalar_float(db: Session, stmt: Select) -> float:
    value = db.scalar(stmt)
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def get_dashboard_kpis(db: Session) -> DashboardKpiResponse:
    products_total = scalar_int(db, select(func.count(PimProduct.id)))
    variants_total = scalar_int(db, select(func.count(PimProductVariant.id)))
    suppliers_total = scalar_int(db, select(func.count(MdmPartner.id)).where(MdmPartner.partner_type == "supplier"))
    purchase_orders_open = scalar_int(
        db, select(func.count(ProcPurchaseOrder.id)).where(ProcPurchaseOrder.status.in_(["draft", "confirmed", "partially_received"]))
    )
    inbound_shipments_active = scalar_int(
        db, select(func.count(InvInboundShipment.id)).where(InvInboundShipment.status.in_(["draft", "in_progress", "discrepancy"]))
    )
    low_stock_alerts_open = scalar_int(
        db, select(func.count(InvStockAlert.id)).where(InvStockAlert.alert_type == "low_stock", InvStockAlert.status == "open")
    )
    stock_value_fifo = scalar_float(db, select(func.sum(InvValuationLayer.remaining_cost)).where(InvValuationLayer.method == "fifo"))
    stock_value_wac = scalar_float(db, select(func.sum(InvValuationLayer.remaining_cost)).where(InvValuationLayer.method == "wac"))

    return DashboardKpiResponse(
        products_total=products_total,
        variants_total=variants_total,
        suppliers_total=suppliers_total,
        purchase_orders_open=purchase_orders_open,
        inbound_shipments_active=inbound_shipments_active,
        low_stock_alerts_open=low_stock_alerts_open,
        stock_value_fifo=stock_value_fifo,
        stock_value_wac=stock_value_wac,
    )
