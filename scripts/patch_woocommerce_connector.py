#!/usr/bin/env python3
"""Patch WooCommerce connector transaction handling for queue jobs.

This script makes the patch reproducible from the parent repository, so we
don't need to commit directly inside the upstream submodule.
"""

from pathlib import Path
import sys


TARGET_DEFAULT = "/mnt/extra-addons/odoo-woocommerce-sync/woocommerce_sync/models/connector.py"

LOGGER_LINES = [
    """            _logger.exception(f'Error syncing WooCommerce product {woocommerce_product["name"]} (WooCommerce product ID: {woocommerce_product["id"]}): {error}')\n""",
    """            _logger.exception(f'Error syncing WooCommerce product: {woocommerce_product["name"]} (WooCommerce product ID: {woocommerce_product["id"]}): {error}')\n""",
    """            _logger.exception(f'Error syncing WooCommerce customer: {woocommerce_customer["first_name"]} {woocommerce_customer["last_name"]} (WooCommerce customer ID: {woocommerce_customer["id"]}): {error}')\n""",
    """            _logger.exception(f'Error syncing WooCommerce order {woocommerce_order["id"]}: {error}')\n""",
]


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(TARGET_DEFAULT)
    if not target.exists():
        print(f"Target file not found: {target}")
        return 1

    text = target.read_text(encoding="utf-8")
    original = text

    # Rolling back inside queue_job_cron_jobrunner savepoints breaks transaction
    # state and can crash the job runner with InvalidSavepointSpecification.
    text = text.replace("            # Roll back changes\n            self.env.cr.rollback()\n", "")

    inserted = 0
    for line in LOGGER_LINES:
        with_raise = f"{line}            raise\n"
        if with_raise in text:
            continue
        if line in text:
            text = text.replace(line, with_raise, 1)
            inserted += 1

    if "self.env.cr.rollback()" in text:
        print("Patch failed: rollback calls still present in connector.py")
        return 2

    if text == original:
        print("Patch already applied or not needed.")
        return 0

    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"Patch applied to {target} (logger raise inserts: {inserted})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
