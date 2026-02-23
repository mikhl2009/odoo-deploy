#!/usr/bin/env python3
"""
scripts/test_connections.py
═══════════════════════════
Test all external connections before going live.

Usage:
    python scripts/test_connections.py \
        --woo-url https://snussidan.se \
        --woo-key ck_xxx \
        --woo-secret cs_xxx \
        --wgr-url https://api.wgr.example.com/rpc \
        --wgr-user api-user \
        --wgr-pass api-pass \
        --nshift-dev-id developer_id \
        --nshift-api-key api_key \
        --api-url http://localhost:8080
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import httpx


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(label: str, detail: str) -> None:
    print(f"  {GREEN}✓{RESET} {label}: {detail}")


def fail(label: str, detail: str) -> None:
    print(f"  {RED}✗{RESET} {label}: {detail}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def timed_post(url: str, json_body: Any, auth: tuple | None = None, timeout: int = 15) -> tuple[dict | None, int, int]:
    """Returns (body | None, status_code, elapsed_ms). status=0 on network error."""
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=json_body, auth=auth)
        elapsed = int((time.monotonic() - t0) * 1000)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:200]}
        return body, resp.status_code, elapsed
    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        return {"error": str(exc)}, 0, elapsed


def timed_get(url: str, auth: tuple | None = None, params: dict | None = None, timeout: int = 15) -> tuple[dict | None, int, int]:
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, auth=auth, params=params)
        elapsed = int((time.monotonic() - t0) * 1000)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:200]}
        return body, resp.status_code, elapsed
    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        return {"error": str(exc)}, 0, elapsed


# ─────────────────────────────────────────────────────────────────────────────
# Individual tests
# ─────────────────────────────────────────────────────────────────────────────


def test_wgr_stock(wgr_url: str, wgr_user: str, wgr_pass: str) -> bool:
    section("1. WGR API — Stock.get")
    body, status, elapsed = timed_post(
        wgr_url,
        json_body={"jsonrpc": "2.0", "method": "Stock.get", "params": {}, "id": 1},
        auth=(wgr_user, wgr_pass),
    )
    if status == 200 and body and "result" in body:
        count = len(body["result"]) if isinstance(body["result"], list) else "?"
        ok("WGR Stock.get", f"{count} artiklar, {elapsed} ms")
        return True
    fail("WGR Stock.get", f"status={status} elapsed={elapsed}ms body={json.dumps(body)[:120]}")
    return False


def test_wgr_orders(wgr_url: str, wgr_user: str, wgr_pass: str) -> bool:
    section("2. WGR API — Order.get (senaste 24h)")
    from datetime import UTC, datetime, timedelta

    from_time = (datetime.now(tz=UTC) - timedelta(hours=24)).isoformat()
    body, status, elapsed = timed_post(
        wgr_url,
        json_body={"jsonrpc": "2.0", "method": "Order.get", "params": {"fromTime": from_time}, "id": 1},
        auth=(wgr_user, wgr_pass),
    )
    if status == 200 and body and "result" in body:
        count = len(body["result"]) if isinstance(body["result"], list) else "?"
        ok("WGR Order.get", f"{count} ordrar, {elapsed} ms")
        return True
    fail("WGR Order.get", f"status={status} elapsed={elapsed}ms body={json.dumps(body)[:120]}")
    return False


def test_woo_status(woo_url: str, woo_key: str, woo_secret: str) -> bool:
    section("3. WooCommerce — system_status")
    url = f"{woo_url.rstrip('/')}/wp-json/wc/v3/system_status"
    body, status, elapsed = timed_get(url, auth=(woo_key, woo_secret))
    if status == 200:
        wc_ver = (body or {}).get("environment", {}).get("version", "?") if isinstance(body, dict) else "?"
        ok("WooCommerce system_status", f"WC {wc_ver}, {elapsed} ms")
        return True
    fail("WooCommerce system_status", f"status={status} elapsed={elapsed}ms")
    return False


def test_woo_products(woo_url: str, woo_key: str, woo_secret: str) -> bool:
    section("4. WooCommerce — products (3 st)")
    url = f"{woo_url.rstrip('/')}/wp-json/wc/v3/products"
    body, status, elapsed = timed_get(url, auth=(woo_key, woo_secret), params={"per_page": "3"})
    if status == 200 and isinstance(body, list):
        ok("WooCommerce products", f"{len(body)} produkter returnerade, {elapsed} ms")
        return True
    fail("WooCommerce products", f"status={status} elapsed={elapsed}ms")
    return False


def test_unified_health(api_url: str) -> bool:
    section("5. Unified API — health check")
    url = f"{api_url.rstrip('/')}/"
    body, status, elapsed = timed_get(url)
    if status == 200:
        ok("Unified API /", f"{elapsed} ms — {json.dumps(body)[:80]}")
        return True
    fail("Unified API /", f"status={status} elapsed={elapsed}ms")
    return False


def test_unified_wgr_test(api_url: str, api_token: str) -> bool:
    section("6. Unified API — WGR connection test (id=1)")
    url = f"{api_url.rstrip('/')}/api/v1/integration/wgr/connections/1/test"
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(url, headers={"Authorization": f"Bearer {api_token}"})
        elapsed = int((time.monotonic() - t0) * 1000)
        body = resp.json()
        if resp.status_code == 200 and body.get("ok"):
            ok("WGR connection test", f"{body.get('article_count')} artiklar, {body.get('response_ms')} ms API, {elapsed} ms total")
            return True
        fail("WGR connection test", f"status={resp.status_code} body={json.dumps(body)[:120]}")
        return False
    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        fail("WGR connection test", f"{exc} ({elapsed} ms)")
        return False


def test_simulated_woo_webhook(api_url: str, api_token: str) -> bool:
    section("7. Simulera WooCommerce-webhook — POST order (connection_id=1)")
    url = f"{api_url.rstrip('/')}/api/v1/integration/woo/webhooks/1/orders"
    sample_payload = {
        "id": 99999,
        "status": "processing",
        "currency": "SEK",
        "billing": {
            "first_name": "Test",
            "last_name": "Testsson",
            "email": "test@example.com",
            "address_1": "Testgatan 1",
            "postcode": "12345",
            "city": "Stockholm",
            "country": "SE",
        },
        "shipping": {
            "first_name": "Test",
            "last_name": "Testsson",
            "address_1": "Testgatan 1",
            "postcode": "12345",
            "city": "Stockholm",
            "country": "SE",
        },
        "line_items": [
            {
                "id": 1,
                "name": "Test produkt",
                "sku": "TEST-001",
                "quantity": 1,
                "price": "99.00",
                "total": "99.00",
            }
        ],
        "shipping_total": "0.00",
        "total": "99.00",
    }
    t0 = time.monotonic()
    try:
        with httpx.Client(timeout=20) as client:
            resp = client.post(
                url,
                json=sample_payload,
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "X-WC-Webhook-Event": "order.created",
                    "X-WC-Webhook-ID": "99999",
                },
            )
        elapsed = int((time.monotonic() - t0) * 1000)
        if resp.status_code in (200, 201, 202):
            ok("WooCommerce webhook simulation", f"status={resp.status_code}, {elapsed} ms")
            return True
        # 404/422/etc — route may not accept test data; still informational
        fail("WooCommerce webhook simulation", f"status={resp.status_code} elapsed={elapsed}ms body={resp.text[:120]}")
        return False
    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        fail("WooCommerce webhook simulation", f"{exc} ({elapsed} ms)")
        return False


def test_nshift_printers(nshift_base: str, dev_id: str, api_key: str) -> bool:
    section("8. nShift — GET /print/printers")
    url = f"{nshift_base.rstrip('/')}/print/printers"
    body, status, elapsed = timed_get(url, auth=(dev_id, api_key))
    if status == 200:
        count = len(body) if isinstance(body, list) else "?"
        ok("nShift printers", f"{count} skrivare, {elapsed} ms")
        return True
    fail("nShift printers", f"status={status} elapsed={elapsed}ms body={json.dumps(body)[:120]}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Test all system connections")
    parser.add_argument("--woo-url", default="")
    parser.add_argument("--woo-key", default="")
    parser.add_argument("--woo-secret", default="")
    parser.add_argument("--wgr-url", default="")
    parser.add_argument("--wgr-user", default="")
    parser.add_argument("--wgr-pass", default="")
    parser.add_argument("--nshift-base", default="https://api.unifaun.com/rs-extapi/v1")
    parser.add_argument("--nshift-dev-id", default="")
    parser.add_argument("--nshift-api-key", default="")
    parser.add_argument("--api-url", default="http://localhost:8080")
    parser.add_argument("--api-token", default="", help="JWT bearer token for Unified API")
    args = parser.parse_args()

    print(f"\n{BOLD}═══ Unified Platform — Connection Test ═══{RESET}\n")

    results: list[bool] = []

    if args.wgr_url:
        results.append(test_wgr_stock(args.wgr_url, args.wgr_user, args.wgr_pass))
        results.append(test_wgr_orders(args.wgr_url, args.wgr_user, args.wgr_pass))
    else:
        print("\n  (WGR skipped — --wgr-url not provided)")
        results += [None, None]  # type: ignore[list-item]

    if args.woo_url:
        results.append(test_woo_status(args.woo_url, args.woo_key, args.woo_secret))
        results.append(test_woo_products(args.woo_url, args.woo_key, args.woo_secret))
    else:
        print("\n  (WooCommerce skipped — --woo-url not provided)")
        results += [None, None]  # type: ignore[list-item]

    results.append(test_unified_health(args.api_url))

    if args.api_token:
        results.append(test_unified_wgr_test(args.api_url, args.api_token))
        results.append(test_simulated_woo_webhook(args.api_url, args.api_token))
    else:
        print("\n  (Unified API authenticated tests skipped — --api-token not provided)")
        results += [None, None]  # type: ignore[list-item]

    if args.nshift_dev_id and args.nshift_api_key:
        results.append(test_nshift_printers(args.nshift_base, args.nshift_dev_id, args.nshift_api_key))
    else:
        print("\n  (nShift skipped — --nshift-dev-id/--nshift-api-key not provided)")
        results.append(None)  # type: ignore[list-item]

    # Summary
    actual = [r for r in results if r is not None]
    passed = sum(1 for r in actual if r)
    failed = sum(1 for r in actual if not r)

    print(f"\n{BOLD}═══ Sammanfattning ═══{RESET}")
    print(f"  Körda:      {len(actual)}")
    print(f"  {GREEN}Godkända:  {passed}{RESET}")
    if failed:
        print(f"  {RED}Misslyckade: {failed}{RESET}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
