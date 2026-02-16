from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class MdmPartner(Base, TimestampMixin):
    __tablename__ = "mdm_partner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    partner_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_no: Mapped[str | None] = mapped_column(String(64))
    vat_no: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    country_code: Mapped[str | None] = mapped_column(String(2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    supplier_profile: Mapped["MdmSupplierProfile | None"] = relationship(back_populates="partner", uselist=False)


class MdmSupplierProfile(Base):
    __tablename__ = "mdm_supplier_profile"

    partner_id: Mapped[int] = mapped_column(ForeignKey("mdm_partner.id"), primary_key=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    payment_terms: Mapped[str | None] = mapped_column(String(128))
    incoterm: Mapped[str | None] = mapped_column(String(32))
    default_currency: Mapped[str | None] = mapped_column(String(3))
    min_order_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    note: Mapped[str | None] = mapped_column(Text)

    partner: Mapped[MdmPartner] = relationship(back_populates="supplier_profile")
