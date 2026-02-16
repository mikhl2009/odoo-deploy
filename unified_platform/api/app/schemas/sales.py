from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import ORMModel


class CustomerCreate(BaseModel):
    customer_type: str = "b2c"
    email: str
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    phone: str | None = None
    credit_limit: Decimal | None = None
    payment_terms: str | None = None


class CustomerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    phone: str | None = None
    credit_limit: Decimal | None = None
    payment_terms: str | None = None
    status: str | None = None


class CustomerResponse(ORMModel):
    id: int
    customer_type: str
    email: str
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    status: str
    tier_id: int | None = None


class CustomerTierAssignRequest(BaseModel):
    tier_id: int | None = None


class OrderLineCreate(BaseModel):
    variant_id: int | None = None
    sku_snapshot: str | None = None
    name_snapshot: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal("0")
    tax_rate: Decimal | None = None


class SalesOrderCreate(BaseModel):
    company_id: int
    order_number: str
    channel_type: str
    store_connection_id: int | None = None
    external_order_id: str | None = None
    customer_id: int | None = None
    warehouse_location_id: int | None = None
    currency_code: str = "SEK"
    shipping_total: Decimal = Decimal("0")
    lines: list[OrderLineCreate]


class SalesOrderResponse(ORMModel):
    id: int
    company_id: int
    order_number: str
    channel_type: str
    status: str
    total: Decimal
    customer_id: int | None = None


class OrderLifecycleAction(BaseModel):
    note: str | None = None
    tracking_number: str | None = None
    carrier_name: str | None = None


class ReturnCreate(BaseModel):
    reason: str | None = None
    return_number: str | None = None


class RefundCreate(BaseModel):
    amount: Decimal
    reason: str | None = None
    status: str = "processed"
