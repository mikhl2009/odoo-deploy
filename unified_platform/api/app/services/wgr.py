from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1, 2, 4]


class WGRClient:
    """JSON-RPC client for Wikinggruppen (WGR) warehouse API."""

    def __init__(self, api_url: str, username: str, password: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._auth = (username, password)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call(self, method: str, params: dict) -> dict:
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        last_exc: Exception | None = None
        for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
            if delay:
                await asyncio.sleep(delay)
            t0 = time.monotonic()
            try:
                async with httpx.AsyncClient(auth=self._auth, timeout=30) as client:
                    resp = await client.post(self._api_url, json=payload)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.info(
                    "WGR %s status=%s elapsed_ms=%d attempt=%d",
                    method,
                    resp.status_code,
                    elapsed_ms,
                    attempt,
                )
                resp.raise_for_status()
                return resp.json()
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning("WGR network error attempt %d/%d: %s", attempt, len(_RETRY_DELAYS) + 1, exc)
        raise last_exc  # type: ignore[misc]

    async def _batch_call(self, commands: list[dict]) -> list[dict]:
        """Send a JSON-RPC batch request."""
        batch = [
            {"jsonrpc": "2.0", "method": cmd["method"], "params": cmd.get("params", {}), "id": i}
            for i, cmd in enumerate(commands, start=1)
        ]
        last_exc: Exception | None = None
        for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
            if delay:
                await asyncio.sleep(delay)
            t0 = time.monotonic()
            try:
                async with httpx.AsyncClient(auth=self._auth, timeout=30) as client:
                    resp = await client.post(self._api_url, json=batch)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.info("WGR batch len=%d status=%s elapsed_ms=%d attempt=%d", len(batch), resp.status_code, elapsed_ms, attempt)
                resp.raise_for_status()
                results: list[dict] = resp.json()
                # Sort by id to preserve original order
                results.sort(key=lambda r: r.get("id", 0))
                return results
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning("WGR batch network error attempt %d/%d: %s", attempt, len(_RETRY_DELAYS) + 1, exc)
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _strip_suffix(article_number: str) -> str:
        """Strip trailing '-01' from WGR article numbers."""
        if article_number.endswith("-01"):
            return article_number[:-3]
        return article_number

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_stock(self, updated_from: datetime | None = None) -> list[dict]:
        """Fetch stock levels. If updated_from supplied, only changed articles."""
        params: dict = {}
        if updated_from is not None:
            params["updatedFrom"] = updated_from.isoformat()
        data = await self._call("Stock.get", params)
        result = data.get("result", []) or []
        for item in result:
            if "articleNumber" in item:
                item["articleNumber"] = self._strip_suffix(item["articleNumber"])
        return result

    async def set_stock(self, article_number: str, qty: int) -> bool:
        """Update stock level for one article in WGR."""
        data = await self._call("Stock.set", {"articleNumber": article_number + "-01", "stock": qty})
        return bool(data.get("result"))

    async def get_orders(self, from_time: datetime | None = None) -> list[dict]:
        """Fetch orders from WGR. Strips '-01' suffix from all article numbers in items."""
        params: dict = {}
        if from_time is not None:
            params["fromTime"] = from_time.isoformat()
        data = await self._call("Order.get", params)
        orders: list[dict] = data.get("result", []) or []
        for order in orders:
            for item in order.get("items", []):
                if "articleNumber" in item:
                    item["articleNumber"] = self._strip_suffix(item["articleNumber"])
        return orders

    async def set_order_status(self, order_id: int, status_id: int) -> bool:
        """Update WGR order status."""
        data = await self._call("Order.set", {"id": order_id, "orderStatus": status_id})
        return bool(data.get("result"))

    async def batch(self, commands: list[dict]) -> list[dict]:
        """Send multiple JSON-RPC commands in a single HTTP call."""
        return await self._batch_call(commands)
