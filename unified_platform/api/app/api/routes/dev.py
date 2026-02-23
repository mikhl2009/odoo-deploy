"""
WGR JSON-RPC mock endpoint — for development and end-to-end testing.

Set WGR_API_URL=https://api.snushallen.cloud/api/v1/dev/wgr to route all WGR
calls here instead of the real Wikinggruppen API.

Supported methods (matching what WGRClient sends):
  Stock.get         → list of {articleNumber, stock} using real PIM SKUs
  Order.get         → 1-2 fake orders with real SKUs picked at random from PIM
  Order.set         → acknowledge status update (WGRClient.set_order_status)
  Stock.set         → acknowledge stock write (WGRClient.set_stock)

No auth required (BasicAuth header is accepted but ignored).
"""
from __future__ import annotations

import logging
import random
import string
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.inventory import InvStockBalance
from app.models.pim import PimProductVariant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev", tags=["dev-mock"])

_FAKE_NAMES = [
    "Erik Svensson", "Anna Lindqvist", "Lars Nilsson",
    "Sofia Johansson", "Magnus Bergström",
]
_FAKE_STREETS = [
    "Kungsgatan 12", "Drottninggatan 5", "Storgatan 3", "Vasagatan 9",
]
_FAKE_CITIES = [
    ("Stockholm", "11122"), ("Göteborg", "41108"), ("Malmö", "21120"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ok(result, req_id) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(code: int, message: str, req_id) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _rand_suffix(n: int = 5) -> str:
    return "".join(random.choices(string.digits, k=n))


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/wgr",
    summary="WGR JSON-RPC mock (dev only)",
    response_model=None,
)
def wgr_mock(body: dict, db: Session = Depends(get_db)) -> dict:
    """
    Simulates the Wikinggruppen JSON-RPC API.
    Point WGR_API_URL to this endpoint for integration testing.
    """
    # Support both single-call and batch JSON-RPC
    if isinstance(body, list):
        return [_dispatch(item, db) for item in body]
    return _dispatch(body, db)


def _dispatch(item: dict, db: Session) -> dict:
    method = item.get("method", "")
    params = item.get("params", {}) or {}
    req_id = item.get("id", 1)

    logger.info("[WGR-MOCK] method=%s params=%s", method, params)

    if method == "Stock.get":
        return _stock_get(params, req_id, db)
    if method == "Stock.set":
        return _ok(True, req_id)
    if method == "Order.get":
        return _order_get(params, req_id, db)
    if method in ("Order.set", "Order.setOrderStatus"):
        return _order_set(params, req_id)
    return _err(-32601, f"Method not found: {method}", req_id)


# ─────────────────────────────────────────────────────────────────────────────
# Method handlers
# ─────────────────────────────────────────────────────────────────────────────

def _stock_get(params: dict, req_id, db: Session) -> dict:
    """
    Return stock for all active variants.
    Uses InvStockBalance.on_hand_qty when available, otherwise random 1-50.
    WGRClient.get_stock() expects result = list[{articleNumber, stock}].
    """
    rows = db.execute(
        select(PimProductVariant.sku, InvStockBalance.on_hand_qty)
        .outerjoin(InvStockBalance, InvStockBalance.variant_id == PimProductVariant.id)
        .where(PimProductVariant.active.is_(True))
        .limit(500)
    ).all()

    stock_list = [
        {
            "articleNumber": sku,          # WGRClient will strip -01 suffix if present
            "stock": int(qty) if qty is not None else random.randint(1, 50),
        }
        for sku, qty in rows
    ]

    logger.info("[WGR-MOCK] Stock.get → %d items", len(stock_list))
    return _ok(stock_list, req_id)


def _order_get(params: dict, req_id, db: Session) -> dict:
    """
    Return 0-2 fake orders with real SKUs from PIM.
    WGRClient.get_orders() expects result = list[order] where
    each order has .items = list[{articleNumber, qty, ...}].
    """
    variants = db.scalars(
        select(PimProductVariant)
        .where(PimProductVariant.active.is_(True))
        .order_by(func.random())
        .limit(6)
    ).all()

    if not variants:
        logger.info("[WGR-MOCK] Order.get → no variants in PIM, returning []")
        return _ok([], req_id)

    num_orders = random.randint(0, min(2, len(variants)))
    orders = []
    now = datetime.now(UTC)

    for i in range(num_orders):
        # Pick 1-2 variants per order, no duplicates across orders
        order_variants = variants[i * 2 : i * 2 + random.randint(1, 2)]
        suffix = _rand_suffix()
        city, post = random.choice(_FAKE_CITIES)

        orders.append(
            {
                "orderId": f"MOCK-{suffix}",
                "orderDate": (now - timedelta(minutes=random.randint(5, 90))).isoformat(),
                "status": 1,  # WGR status 1 = new
                "items": [
                    {
                        "articleNumber": v.sku,
                        "qty": random.randint(1, 3),
                        "unitPrice": round(random.uniform(49.0, 299.0), 2),
                    }
                    for v in order_variants
                ],
                "deliveryAddress": {
                    "name": random.choice(_FAKE_NAMES),
                    "address1": random.choice(_FAKE_STREETS),
                    "city": city,
                    "postalCode": post,
                    "countryCode": "SE",
                    "email": f"test+{suffix}@example.com",
                    "phone": f"+4670{suffix}",
                },
            }
        )

    logger.info("[WGR-MOCK] Order.get → %d orders", len(orders))
    return _ok(orders, req_id)


def _order_set(params: dict, req_id) -> dict:
    """Acknowledge order status update."""
    order_id = params.get("id") or params.get("orderId")
    status_val = params.get("orderStatus") or params.get("status")
    logger.info("[WGR-MOCK] Order.set orderId=%s status=%s → OK", order_id, status_val)
    return _ok(True, req_id)
