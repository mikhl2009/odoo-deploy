from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import TimestampMixin


class InvInboundShipment(Base, TimestampMixin):
    __tablename__ = "inv_inbound_shipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    po_id: Mapped[int | None] = mapped_column(ForeignKey("proc_purchase_order.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("mdm_partner.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    asn_number: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    expected_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receiver_user_id: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)


class InvInboundShipmentLine(Base, TimestampMixin):
    __tablename__ = "inv_inbound_shipment_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("inv_inbound_shipment.id"), nullable=False)
    po_line_id: Mapped[int | None] = mapped_column(ForeignKey("proc_purchase_order_line.id"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    expected_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    received_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discrepancy_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discrepancy_reason: Mapped[str | None] = mapped_column(Text)


class InvLot(Base, TimestampMixin):
    __tablename__ = "inv_lot"
    __table_args__ = (UniqueConstraint("variant_id", "lot_number", name="uq_inv_lot_variant_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    lot_number: Mapped[str] = mapped_column(String(128), nullable=False)
    supplier_lot_number: Mapped[str | None] = mapped_column(String(128))
    production_date: Mapped[str | None] = mapped_column(String(32))
    expiry_date: Mapped[str | None] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class InvTraceContainer(Base, TimestampMixin):
    __tablename__ = "inv_trace_container"
    __table_args__ = (UniqueConstraint("container_code", name="uq_inv_trace_container_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inv_lot.id"))
    container_code: Mapped[str] = mapped_column(String(128), nullable=False)
    level_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_container_id: Mapped[int | None] = mapped_column(ForeignKey("inv_trace_container.id"))
    units_qty: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class InvStockBalance(Base, TimestampMixin):
    __tablename__ = "inv_stock_balance"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "location_id",
            "variant_id",
            "lot_id",
            "container_id",
            name="uq_inv_stock_balance_scope",
        ),
        Index("ix_inv_stock_balance_lookup", "location_id", "variant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inv_lot.id"))
    container_id: Mapped[int | None] = mapped_column(ForeignKey("inv_trace_container.id"))
    on_hand_qty: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    reserved_qty: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    available_qty: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)


class InvStockMovement(Base):
    __tablename__ = "inv_stock_movement"
    __table_args__ = (Index("ix_inv_stock_movement_moved_at", "moved_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_location_id: Mapped[int | None] = mapped_column(ForeignKey("core_location.id"))
    dest_location_id: Mapped[int | None] = mapped_column(ForeignKey("core_location.id"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inv_lot.id"))
    container_id: Mapped[int | None] = mapped_column(ForeignKey("inv_trace_container.id"))
    qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    uom: Mapped[str] = mapped_column(String(16), default="pcs", nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    source_doc_type: Mapped[str | None] = mapped_column(String(64))
    source_doc_id: Mapped[str | None] = mapped_column(String(64))
    moved_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    moved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvValuationLayer(Base, TimestampMixin):
    __tablename__ = "inv_valuation_layer"
    __table_args__ = (Index("ix_inv_valuation_layer_variant", "variant_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movement_id: Mapped[int] = mapped_column(ForeignKey("inv_stock_movement.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    qty_in: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    qty_out: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    remaining_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    remaining_cost: Mapped[float] = mapped_column(Numeric(14, 4), default=0, nullable=False)


class InvReceivingScanEvent(Base):
    __tablename__ = "inv_receiving_scan_event"
    __table_args__ = (Index("ix_inv_receiving_scan_event_scanned_at", "scanned_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("inv_inbound_shipment.id"), nullable=False)
    shipment_line_id: Mapped[int | None] = mapped_column(ForeignKey("inv_inbound_shipment_line.id"))
    scanned_code: Mapped[str] = mapped_column(String(255), nullable=False)
    code_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scan_result: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    device_id: Mapped[str | None] = mapped_column(String(128))
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class InvDiscrepancyReport(Base, TimestampMixin):
    __tablename__ = "inv_discrepancy_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("inv_inbound_shipment.id"), nullable=False)
    shipment_line_id: Mapped[int | None] = mapped_column(ForeignKey("inv_inbound_shipment_line.id"))
    issue_type: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    received_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvReplenishmentRule(Base, TimestampMixin):
    __tablename__ = "inv_replenishment_rule"
    __table_args__ = (
        UniqueConstraint("company_id", "location_id", "variant_id", name="uq_inv_replenishment_rule_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    min_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    max_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reorder_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    preferred_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("mdm_partner.id"))
    lead_time_days_override: Mapped[int | None] = mapped_column(Integer)


class InvStockAlert(Base):
    __tablename__ = "inv_stock_alert"
    __table_args__ = (Index("ix_inv_stock_alert_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvCountSession(Base, TimestampMixin):
    __tablename__ = "inv_count_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    started_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvCountLine(Base, TimestampMixin):
    __tablename__ = "inv_count_line"
    __table_args__ = (UniqueConstraint("session_id", "variant_id", "lot_id", name="uq_inv_count_line_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("inv_count_session.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("inv_lot.id"))
    expected_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    counted_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    diff_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))
    approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
