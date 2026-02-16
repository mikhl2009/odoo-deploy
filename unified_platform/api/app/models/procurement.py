from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class ProcPurchaseOrder(Base, TimestampMixin):
    __tablename__ = "proc_purchase_order"
    __table_args__ = (UniqueConstraint("company_id", "po_number", name="uq_proc_purchase_order_company_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    po_number: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("mdm_partner.id"), nullable=False)
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_terms: Mapped[str | None] = mapped_column(String(128))
    expected_date: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))

    lines: Mapped[list["ProcPurchaseOrderLine"]] = relationship(back_populates="po", cascade="all, delete-orphan")


class ProcPurchaseOrderLine(Base, TimestampMixin):
    __tablename__ = "proc_purchase_order_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("proc_purchase_order.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    ordered_qty: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    received_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    tax_rate: Mapped[float | None] = mapped_column(Numeric(7, 4))
    expected_date: Mapped[str | None] = mapped_column(String(64))

    po: Mapped[ProcPurchaseOrder] = relationship(back_populates="lines")
