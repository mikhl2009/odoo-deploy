from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class PimBrand(Base, TimestampMixin):
    __tablename__ = "pim_brand"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_pim_brand_company_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PimCategory(Base, TimestampMixin):
    __tablename__ = "pim_category"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_pim_category_company_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("pim_category.id"))
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PimProduct(Base, TimestampMixin):
    __tablename__ = "pim_product"
    __table_args__ = (
        UniqueConstraint("company_id", "sku", name="uq_pim_product_company_sku"),
        Index("ix_pim_product_lookup", "company_id", "sku", "ean"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(128), nullable=False)
    ean: Mapped[str | None] = mapped_column(String(32))
    gtin14: Mapped[str | None] = mapped_column(String(14))
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("pim_brand.id"))
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    product_type: Mapped[str] = mapped_column(String(32), default="simple", nullable=False)
    is_tobacco: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    variants: Mapped[list["PimProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    translations: Mapped[list["PimProductI18n"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class PimProductI18n(Base):
    __tablename__ = "pim_product_i18n"
    __table_args__ = (UniqueConstraint("product_id", "language_code", name="uq_pim_product_i18n"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("pim_product.id"), nullable=False)
    language_code: Mapped[str] = mapped_column(String(5), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_desc: Mapped[str | None] = mapped_column(Text)
    long_desc: Mapped[str | None] = mapped_column(Text)
    health_warning_text: Mapped[str | None] = mapped_column(Text)

    product: Mapped[PimProduct] = relationship(back_populates="translations")


class PimProductVariant(Base, TimestampMixin):
    __tablename__ = "pim_product_variant"
    __table_args__ = (
        UniqueConstraint("product_id", "sku", name="uq_pim_product_variant_product_sku"),
        Index("ix_pim_product_variant_sku_ean", "sku", "ean"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("pim_product.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(128), nullable=False)
    ean: Mapped[str | None] = mapped_column(String(32))
    barcode: Mapped[str | None] = mapped_column(String(128))
    weight_g: Mapped[float | None] = mapped_column(Numeric(12, 3))
    length_mm: Mapped[float | None] = mapped_column(Numeric(12, 2))
    width_mm: Mapped[float | None] = mapped_column(Numeric(12, 2))
    height_mm: Mapped[float | None] = mapped_column(Numeric(12, 2))
    nicotine_mg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    tpd_code: Mapped[str | None] = mapped_column(String(128))
    tax_class: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[PimProduct] = relationship(back_populates="variants")


class PimAttributeDef(Base, TimestampMixin):
    __tablename__ = "pim_attribute_def"
    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_pim_attribute_def_company_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_variant_axis: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PimAttributeValue(Base):
    __tablename__ = "pim_attribute_value"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attribute_def_id: Mapped[int] = mapped_column(ForeignKey("pim_attribute_def.id"), nullable=False)
    value_text: Mapped[str | None] = mapped_column(String(255))
    value_number: Mapped[float | None] = mapped_column(Numeric(12, 4))
    value_bool: Mapped[bool | None] = mapped_column(Boolean)


class PimVariantAttributeMap(Base):
    __tablename__ = "pim_variant_attribute_map"
    __table_args__ = (UniqueConstraint("variant_id", "attribute_value_id", name="uq_pim_variant_attribute"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    attribute_value_id: Mapped[int] = mapped_column(ForeignKey("pim_attribute_value.id"), nullable=False)


class PimTag(Base):
    __tablename__ = "pim_tag"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_pim_tag_company_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class PimProductTagMap(Base):
    __tablename__ = "pim_product_tag_map"
    __table_args__ = (UniqueConstraint("product_id", "tag_id", name="uq_pim_product_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("pim_product.id"), nullable=False)
    tag_id: Mapped[int] = mapped_column(ForeignKey("pim_tag.id"), nullable=False)


class PimProductCategoryMap(Base):
    __tablename__ = "pim_product_category_map"
    __table_args__ = (UniqueConstraint("product_id", "category_id", name="uq_pim_product_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("pim_product.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("pim_category.id"), nullable=False)


class PimMediaAsset(Base, TimestampMixin):
    __tablename__ = "pim_media_asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("pim_product.id"))
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("pim_product_variant.id"))
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255))


class PimPriceList(Base, TimestampMixin):
    __tablename__ = "pim_price_list"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_pim_price_list_company_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[str | None] = mapped_column(String(64))
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    valid_from: Mapped[str | None] = mapped_column(String(32))
    valid_to: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PimPriceListItem(Base, TimestampMixin):
    __tablename__ = "pim_price_list_item"
    __table_args__ = (UniqueConstraint("price_list_id", "variant_id", "min_qty", name="uq_pim_price_list_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    price_list_id: Mapped[int] = mapped_column(ForeignKey("pim_price_list.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    min_qty: Mapped[float] = mapped_column(Numeric(12, 2), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    customer_tier_code: Mapped[str | None] = mapped_column(String(64))


class PimRevision(Base):
    __tablename__ = "pim_revision"
    __table_args__ = (Index("ix_pim_revision_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_jsonb: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    changed_at: Mapped[str] = mapped_column(String(64), nullable=False)
