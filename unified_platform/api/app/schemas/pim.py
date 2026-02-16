from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import ORMModel


class ProductI18nPayload(BaseModel):
    language_code: str
    name: str
    short_desc: str | None = None
    long_desc: str | None = None
    health_warning_text: str | None = None


class ProductCreate(BaseModel):
    company_id: int
    sku: str
    ean: str | None = None
    gtin14: str | None = None
    brand_id: int | None = None
    status: str = "draft"
    product_type: str = "simple"
    is_tobacco: bool = True
    translations: list[ProductI18nPayload]


class ProductUpdate(BaseModel):
    sku: str | None = None
    ean: str | None = None
    gtin14: str | None = None
    brand_id: int | None = None
    status: str | None = None
    product_type: str | None = None
    is_tobacco: bool | None = None


class ProductVariantCreate(BaseModel):
    sku: str
    ean: str | None = None
    barcode: str | None = None
    weight_g: Decimal | None = None
    length_mm: Decimal | None = None
    width_mm: Decimal | None = None
    height_mm: Decimal | None = None
    nicotine_mg: Decimal | None = None
    tpd_code: str | None = None
    tax_class: str | None = None
    active: bool = True


class ProductVariantUpdate(BaseModel):
    barcode: str | None = None
    tax_class: str | None = None
    active: bool | None = None
    nicotine_mg: Decimal | None = None
    tpd_code: str | None = None


class ProductResponse(ORMModel):
    id: int
    company_id: int
    sku: str
    ean: str | None = None
    status: str
    product_type: str
    is_tobacco: bool


class ProductVariantResponse(ORMModel):
    id: int
    product_id: int
    sku: str
    ean: str | None = None
    tax_class: str | None = None
    active: bool


class ProductMediaCreate(BaseModel):
    company_id: int
    product_id: int | None = None
    variant_id: int | None = None
    media_type: str
    file_url: str
    checksum: str | None = None
    sort_order: int = 0
    alt_text: str | None = None


class PriceBulkItem(BaseModel):
    price_list_id: int
    variant_id: int
    min_qty: Decimal = Decimal("1")
    unit_price: Decimal
    customer_tier_code: str | None = None


class PriceBulkUpsertRequest(BaseModel):
    items: list[PriceBulkItem]


class RevisionResponse(ORMModel):
    id: int
    entity_type: str
    entity_id: str
    revision_no: int
    snapshot_jsonb: dict
    changed_by: int | None = None
    changed_at: str
