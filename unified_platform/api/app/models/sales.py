from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
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


class SalesCustomer(Base, TimestampMixin):
    __tablename__ = "sales_customer"
    __table_args__ = (UniqueConstraint("email", name="uq_sales_customer_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_type: Mapped[str] = mapped_column(String(16), default="b2c", nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    company_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    credit_limit: Mapped[float | None] = mapped_column(Numeric(14, 2))
    payment_terms: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    tier_id: Mapped[int | None] = mapped_column(ForeignKey("sales_customer_tier.id"))


class SalesCustomerAddress(Base, TimestampMixin):
    __tablename__ = "sales_customer_address"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("sales_customer.id"), nullable=False)
    address_type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str | None] = mapped_column(String(128))
    postcode: Mapped[str | None] = mapped_column(String(32))
    country: Mapped[str] = mapped_column(String(2), nullable=False)


class SalesCustomerTier(Base, TimestampMixin):
    __tablename__ = "sales_customer_tier"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_sales_customer_tier_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    discount_percent: Mapped[float | None] = mapped_column(Numeric(7, 4))
    credit_days: Mapped[int | None] = mapped_column(Integer)
    min_order_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SalesOrder(Base, TimestampMixin):
    __tablename__ = "sales_order"
    __table_args__ = (UniqueConstraint("company_id", "order_number", name="uq_sales_order_company_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    order_number: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)
    store_connection_id: Mapped[int | None] = mapped_column(ForeignKey("int_store_connection.id"))
    external_order_id: Mapped[str | None] = mapped_column(String(128))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("sales_customer.id"))
    warehouse_location_id: Mapped[int | None] = mapped_column(ForeignKey("core_location.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    shipping_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    confirmed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    picked_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    packed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


class SalesOrderLine(Base, TimestampMixin):
    __tablename__ = "sales_order_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("pim_product_variant.id"))
    sku_snapshot: Mapped[str | None] = mapped_column(String(128))
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_rate: Mapped[float | None] = mapped_column(Numeric(7, 4))
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    reserved_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    picked_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    shipped_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)


class SalesOrderEvent(Base):
    __tablename__ = "sales_order_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SalesShipment(Base, TimestampMixin):
    __tablename__ = "sales_shipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    shipment_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    carrier_name: Mapped[str | None] = mapped_column(String(128))
    tracking_number: Mapped[str | None] = mapped_column(String(128))
    label_url: Mapped[str | None] = mapped_column(String(255))
    shipped_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


class SalesShipmentLine(Base, TimestampMixin):
    __tablename__ = "sales_shipment_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("sales_shipment.id"), nullable=False)
    order_line_id: Mapped[int] = mapped_column(ForeignKey("sales_order_line.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class SalesInvoice(Base, TimestampMixin):
    __tablename__ = "sales_invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    tax_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    issued_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


class SalesReturn(Base, TimestampMixin):
    __tablename__ = "sales_return"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    return_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="requested", nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    received_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))


class SalesRefund(Base, TimestampMixin):
    __tablename__ = "sales_refund"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    return_id: Mapped[int | None] = mapped_column(ForeignKey("sales_return.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="requested", nullable=False)
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
