from __future__ import annotations

import enum


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class ProductStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class ProductType(str, enum.Enum):
    simple = "simple"
    variable = "variable"


class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    partially_received = "partially_received"
    received = "received"
    canceled = "canceled"


class ShipmentStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    received = "received"
    discrepancy = "discrepancy"
    canceled = "canceled"


class StockMovementType(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    transfer = "transfer"
    adjustment = "adjustment"
    count_adjustment = "count_adjustment"


class ValuationMethod(str, enum.Enum):
    fifo = "fifo"
    wac = "wac"
