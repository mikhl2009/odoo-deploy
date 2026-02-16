from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import ORMModel


class StoreChannelCreate(BaseModel):
    company_id: int
    name: str
    channel_type: str = "woocommerce"
    base_url: str


class StoreConnectionCreate(BaseModel):
    store_channel_id: int
    provider: str = "woocommerce"
    api_base_url: str
    consumer_key: str
    consumer_secret: str
    webhook_secret: str | None = None
    active: bool = True


class StoreConnectionUpdate(BaseModel):
    api_base_url: str | None = None
    consumer_key: str | None = None
    consumer_secret: str | None = None
    webhook_secret: str | None = None
    active: bool | None = None


class StoreConnectionResponse(ORMModel):
    id: int
    store_channel_id: int
    provider: str
    api_base_url: str
    active: bool


class WooWebhookLineItem(BaseModel):
    sku: str | None = None
    name: str
    quantity: int
    price: Decimal | None = None


class WooWebhookOrderPayload(BaseModel):
    id: str
    number: str | None = None
    status: str
    currency: str = "SEK"
    total: Decimal | None = None
    shipping_total: Decimal | None = None
    customer_id: str | None = None
    billing_email: str | None = None
    billing_first_name: str | None = None
    billing_last_name: str | None = None
    line_items: list[WooWebhookLineItem]


class WooBulkVisibilityItem(BaseModel):
    variant_id: int
    visible: bool


class WooBulkVisibilityRequest(BaseModel):
    store_connection_id: int
    items: list[WooBulkVisibilityItem]


class WooBulkPriceItem(BaseModel):
    variant_id: int
    web_price: Decimal


class WooBulkPricingRequest(BaseModel):
    store_connection_id: int
    items: list[WooBulkPriceItem]
