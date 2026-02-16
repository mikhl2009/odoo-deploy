from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.schemas.common import ORMModel


class SupplierCreate(BaseModel):
    legal_name: str
    org_no: str | None = None
    vat_no: str | None = None
    email: str | None = None
    phone: str | None = None
    country_code: str | None = None
    lead_time_days: int | None = None
    payment_terms: str | None = None
    incoterm: str | None = None
    default_currency: str | None = None
    min_order_value: Decimal | None = None


class SupplierResponse(ORMModel):
    id: int
    partner_type: str
    legal_name: str
    email: str | None = None


class PurchaseOrderLineCreate(BaseModel):
    variant_id: int
    ordered_qty: Decimal
    unit_cost: Decimal
    tax_rate: Decimal | None = None
    expected_date: str | None = None


class PurchaseOrderCreate(BaseModel):
    company_id: int
    po_number: str
    supplier_id: int
    destination_location_id: int
    currency_code: str = "SEK"
    payment_terms: str | None = None
    expected_date: str | None = None
    lines: list[PurchaseOrderLineCreate]


class PurchaseOrderResponse(ORMModel):
    id: int
    company_id: int
    po_number: str
    supplier_id: int
    destination_location_id: int
    status: str


class InboundShipmentCreate(BaseModel):
    company_id: int
    po_id: int | None = None
    supplier_id: int
    source_type: str
    asn_number: str | None = None
    expected_arrival_at: str | None = None
    destination_location_id: int


class InboundShipmentResponse(ORMModel):
    id: int
    company_id: int
    supplier_id: int
    source_type: str
    status: str


class ShipmentScanRequest(BaseModel):
    shipment_line_id: int | None = None
    scanned_code: str
    code_type: str
    scan_result: str
    device_id: str | None = None


class ShipmentDiscrepancyCreate(BaseModel):
    shipment_line_id: int | None = None
    issue_type: str
    expected_qty: Decimal
    received_qty: Decimal
    severity: str
    notes: str | None = None


class InboundShipmentLineCreate(BaseModel):
    po_line_id: int | None = None
    variant_id: int
    expected_qty: Decimal
    received_qty: Decimal = Decimal("0")
    discrepancy_qty: Decimal = Decimal("0")
    discrepancy_reason: str | None = None
