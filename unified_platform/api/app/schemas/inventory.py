from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import ORMModel


class StockBalanceResponse(ORMModel):
    id: int
    company_id: int
    location_id: int
    variant_id: int
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal


class StockMovementCreate(BaseModel):
    company_id: int
    movement_type: str
    source_location_id: int | None = None
    dest_location_id: int | None = None
    variant_id: int
    lot_id: int | None = None
    container_id: int | None = None
    qty: Decimal
    uom: str = "pcs"
    reason_code: str | None = None
    source_doc_type: str | None = None
    source_doc_id: str | None = None


class StockMovementResponse(ORMModel):
    id: int
    company_id: int
    movement_type: str
    variant_id: int
    qty: Decimal
    uom: str


class ReplenishmentRuleCreate(BaseModel):
    company_id: int
    location_id: int
    variant_id: int
    min_qty: Decimal
    max_qty: Decimal
    reorder_qty: Decimal
    preferred_supplier_id: int | None = None
    lead_time_days_override: int | None = None


class CountSessionCreate(BaseModel):
    company_id: int
    location_id: int


class CountLineCreate(BaseModel):
    variant_id: int
    lot_id: int | None = None
    expected_qty: Decimal
    counted_qty: Decimal
    reason_code: str | None = None
