from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_DELAYS = [1, 2, 4]


class NShiftClient:
    """
    nShift Delivery API (Unifaun) integration.
    Base URL: https://api.unifaun.com/rs-extapi/v1
    Auth: BasicAuth(developer_id, api_key)
    """

    def __init__(
        self,
        api_url: str | None = None,
        developer_id: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base_url = (api_url or settings.nshift_api_url).rstrip("/")
        self._auth = (
            developer_id or settings.nshift_developer_id,
            api_key or settings.nshift_api_key,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._base_url}/{path.lstrip('/')}"
        last_exc: Exception | None = None
        for attempt, delay in enumerate([0] + _RETRY_DELAYS, start=1):
            if delay:
                await asyncio.sleep(delay)
            t0 = time.monotonic()
            try:
                async with httpx.AsyncClient(auth=self._auth, timeout=30) as client:
                    resp = await client.request(method, url, **kwargs)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                logger.info(
                    "nShift %s %s status=%s elapsed_ms=%d attempt=%d",
                    method,
                    path,
                    resp.status_code,
                    elapsed_ms,
                    attempt,
                )
                resp.raise_for_status()
                return resp
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                last_exc = exc
                logger.warning("nShift network error attempt %d/%d: %s", attempt, len(_RETRY_DELAYS) + 1, exc)
            except httpx.HTTPStatusError:
                raise
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_shipment_and_print(
        self,
        order,  # SalesOrder — avoid import cycle with type annotation
        order_lines: list,
        printer_id: str,
        packed_by: str,
    ) -> dict:
        """
        Create a shipment and trigger Cloud Print in one call.
        Returns: {shipment_id, tracking_number, status}
        """
        # Derive shipping fields — SalesOrder stores them in JSON metadata or
        # dedicated columns added by the extended model. We access via getattr
        # with sensible fallbacks so this works with the base model too.
        payload = {
            "shipment": {
                "senderReference": packed_by,
                "sender": {"quickId": settings.nshift_sender_quick_id},
                "receiver": {
                    "name": getattr(order, "shipping_name", "") or "",
                    "address1": getattr(order, "shipping_address1", "") or "",
                    "zipCode": getattr(order, "shipping_zip", "") or "",
                    "city": getattr(order, "shipping_city", "") or "",
                    "countryCode": getattr(order, "shipping_country", "SE") or "SE",
                },
                "service": {"id": getattr(order, "shipping_service_id", "SE-000101") or "SE-000101"},
                "options": [
                    {"id": "enot", "to": getattr(order, "customer_email", "") or ""}
                ],
                "parcels": [{"copies": 1}],
            },
            "printConfig": {
                "target1Media": "laser-a5",
                "target1Printer": printer_id,
            },
        }
        resp = await self._request("POST", "/shipments", json=payload)
        data = resp.json()
        # nShift returns a list; take the first shipment
        shipments = data if isinstance(data, list) else [data]
        first = shipments[0] if shipments else {}
        tracking = ""
        for parcel in first.get("parcels", []):
            tracking = parcel.get("parcelNo", "") or parcel.get("packageNo", "")
            if tracking:
                break
        return {
            "shipment_id": first.get("id", ""),
            "tracking_number": tracking,
            "status": first.get("status", "unknown"),
        }

    async def get_printers(self) -> list[dict]:
        """List available Cloud Print printers."""
        resp = await self._request("GET", "/print/printers")
        return resp.json() if resp.content else []

    async def get_shipment_history(
        self,
        date_from: datetime,
        sender_reference: str | None = None,
    ) -> list[dict]:
        """
        Retrieve shipment history from nShift.
        Filter on senderReference (packed_by) if provided.
        """
        params: dict = {"from": date_from.strftime("%Y-%m-%d")}
        if sender_reference:
            params["senderReference"] = sender_reference
        resp = await self._request("GET", "/shipments-history", params=params)
        return resp.json() if resp.content else []

    async def cancel_shipment(self, shipment_id: str) -> bool:
        """Cancel/delete a shipment before EDI transmission."""
        await self._request("DELETE", f"/shipments/{shipment_id}")
        return True
