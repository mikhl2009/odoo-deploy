#!/usr/bin/env python3
"""
Install all Odoo modules needed for a complete ERP covering every department.

Installs Odoo core apps first, then OCA community modules, in dependency order.
Uses XML-RPC so it can run from any machine with network access.

Usage:
    python install_all_departments.py
    python install_all_departments.py --url https://snushallen.cloud --db odoo_production
"""
import xmlrpc.client
import argparse
import time
import sys

# ── connection defaults ────────────────────────────────────────────────
DEFAULT_URL = "https://snushallen.cloud"
DEFAULT_DB = "odoo"
DEFAULT_USER = "mikael@snushallen.se"
DEFAULT_PASSWORD = "a04315610102c5d4cde37f7c8afea09d8721569a"  # API key
MODULE_INSTALL_RETRIES = 6
MODULE_INSTALL_RETRY_WAIT = 20


# ── modules per department ─────────────────────────────────────────────
# Each tuple: (module_technical_name, human description)
# Order matters – dependencies must come first.

CORE_MODULES = [
    # ── Fundamental ──
    ("contacts", "Kontakthantering"),
    ("mail", "Diskussioner / Intern chatt"),
    ("calendar", "Kalender"),

    # ── Försäljning ──
    ("sale_management", "Försäljning"),
    ("crm", "CRM – Kundrelationer & Pipeline"),

    # ── Inköp ──
    ("purchase", "Inköp"),

    # ── Lager / WMS ──
    ("stock", "Lager / Inventory"),
    ("barcodes", "Streckkoder"),
    # stock_barcode is Enterprise-only; OCA barcode modules used instead

    # ── Ekonomi / Bokföring ──
    ("account", "Bokföring"),
    ("account_payment", "Betalningar"),

    # ── HR / Personal ──
    ("hr", "Personal / Anställda"),
    ("hr_attendance", "Närvaroregistrering"),
    ("hr_holidays", "Frånvaro / Semester"),
    ("hr_expense", "Utlägg"),
    ("hr_recruitment", "Rekrytering"),

    # ── Projekt ──
    ("project", "Projekthantering"),
    ("hr_timesheet", "Tidrapportering"),

    # ── Tillverkning (om relevant) ──
    ("mrp", "Tillverkning / MRP"),

    # ── E-handel ──
    ("website", "Webbplats / Portal"),
    ("website_sale", "Webbshop"),

    # ── Marknadsföring ──
    ("mass_mailing", "E-postmarknadsföring"),

    # account_invoice_extract is Enterprise-only
]

OCA_MODULES = [
    # ── Queue (krävs av WooCommerce) ──
    ("queue_job", "Bakgrundsjobb (OCA Queue)"),
    ("queue_job_cron_jobrunner", "Cron-baserad jobbkörare"),

    # ── Intercompany (OCA Community) ──
    ("account_invoice_inter_company", "Mellanbolagsfakturor"),
    ("purchase_sale_inter_company", "Skapa SO automatiskt från PO mellan bolag"),
    ("purchase_sale_stock_inter_company", "Intercompany med lager/plock-synk"),

    # ── WooCommerce ──
    ("woocommerce_sync", "WooCommerce Sync"),

    # ── Custom ──
    ("prima_wms", "Prima WMS Extension"),

    # ── Lager / Workflow (OCA) ──
    ("stock_no_negative", "Förbjud negativt lagersaldo"),
    ("stock_picking_back2draft", "Återöppna avbrutna leveranser"),
    ("stock_split_picking", "Dela leveranser"),
    ("stock_picking_batch_creation", "Batch-plock"),
    ("stock_picking_auto_create_lot", "Auto-skapa lot vid inleverans"),

    # ── Barcode (OCA) ──
    ("barcodes_generator_product", "Streckkodsgenerator för produkter"),
    ("product_multi_barcode", "Flera streckkoder per produkt"),

    # ── Delivery / Frakt (OCA) ──
    # delivery_auto_refresh requires sale_order_carrier_auto_assign (not available)
    ("delivery_carrier_label_default", "Standard fraktetikett"),
    ("delivery_state", "Spårningsstatus frakt"),

    # ── RMA / Returer (OCA) ──
    ("rma", "Returhantering"),
    ("rma_sale", "Returer från försäljning"),

    # ── Helpdesk / Kundtjänst (OCA) ──
    ("helpdesk_mgmt", "Helpdesk – Ärendehantering"),
    ("helpdesk_mgmt_sla", "Helpdesk SLA"),

    # ── CRM (OCA) ──
    ("crm_phonecall", "CRM Telefonsamtal"),
    ("crm_lead_code", "Sekventiella leads"),

    # ── HR (OCA) ──
    ("hr_employee_firstname", "Förnamn/Efternamn separerat"),
    ("hr_appraisal_oca", "Medarbetarsamtal"),

    # ── Projekt (OCA) ──
    ("project_key", "Projektnycklar"),
    ("project_task_code", "Uppgiftskoder"),
    ("project_timesheet_time_control", "Tidkontroll i projekt"),

    # ── Tillverkning (OCA) ──
    ("quality_control_oca", "Kvalitetskontroll"),
    ("mrp_multi_level", "MRP Scheduler"),

    # ── Beroenden för rapporter (OCA) ──
    ("date_range", "Datumintervall (beroende)"),
    ("report_xlsx", "Excel-rapporter (beroende)"),

    # ── Ekonomi / Rapporter (OCA) ──
    ("account_financial_report", "Finansrapporter (OCA)"),
    ("account_tax_balance", "Skattebalans"),
    ("partner_statement", "Kontoutdrag kund/leverantör"),

    # ── Produkthantering (OCA) ──
    ("product_sequence", "Produktsekvenser"),
    ("product_manufacturer", "Tillverkare på produkt"),
    ("product_state", "Produktstatus / Livscykel"),
    ("product_variant_default_code", "Auto-generera artikelnummer varianter"),

    # ── Print / Etikett (OCA) ──
    # base_report_to_printer + printer_zpl2 require pycups (CUPS print server) - enable if needed
    # ("base_report_to_printer", "Skriv ut rapporter direkt"),
    # ("printer_zpl2", "ZPL2 etikettskrivare"),

    # ── Social / Meddelanden (OCA) ──
    ("mail_gateway", "Mail Gateway"),

    # ── Server Tools (OCA) ──
    ("auto_backup", "Automatisk databasbackup"),
    ("auditlog", "Granskningslogg"),
    ("module_auto_update", "Auto-uppdatera moduler"),

    # ── Web UI (OCA) ──
    ("web_responsive", "Responsivt gränssnitt"),
    ("web_environment_ribbon", "Miljö-band (dev/staging/prod)"),
    ("web_refresher", "Uppdateringsknapp i huvudmenyn"),
]


def parse_args():
    p = argparse.ArgumentParser(description="Install all Odoo departments")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--user", default=DEFAULT_USER)
    p.add_argument("--password", default=DEFAULT_PASSWORD)
    p.add_argument("--skip-core", action="store_true",
                   help="Skip Odoo core modules (install only OCA)")
    p.add_argument("--skip-oca", action="store_true",
                   help="Skip OCA modules (install only core)")
    p.add_argument("--dry-run", action="store_true",
                   help="Only check availability, don't install")
    p.add_argument("--pause-cron", action="store_true",
                   help="Temporarily disable all scheduled actions during module installation")
    p.add_argument("--cron-wait", type=int, default=30,
                   help="Seconds to wait after pausing cron jobs (default: 30)")
    return p.parse_args()


def connect(url, db, user, password):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        print("Authentication failed!")
        sys.exit(1)
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    print(f"Connected to {url} (db={db}, uid={uid})")
    return uid, models


def update_module_list(models, uid, db, password):
    print("\nUpdating module list...")
    models.execute_kw(db, uid, password,
                      'ir.module.module', 'update_list', [])
    print("Module list updated.")


def pause_scheduled_actions(models, uid, db, password, wait_seconds=30):
    cron_ids = models.execute_kw(
        db, uid, password,
        "ir.cron", "search",
        [[["active", "=", True]]],
    )
    if not cron_ids:
        print("\nNo active scheduled actions to pause.")
        return []
    models.execute_kw(
        db, uid, password,
        "ir.cron", "write",
        [cron_ids, {"active": False}],
    )
    print(f"\nPaused {len(cron_ids)} scheduled actions.")
    if wait_seconds > 0:
        print(f"Waiting {wait_seconds}s for running cron transactions to finish...")
        time.sleep(wait_seconds)
    return cron_ids


def resume_scheduled_actions(models, uid, db, password, cron_ids):
    if not cron_ids:
        return
    models.execute_kw(
        db, uid, password,
        "ir.cron", "write",
        [cron_ids, {"active": True}],
    )
    print(f"Resumed {len(cron_ids)} scheduled actions.")


def install_module(models, uid, db, password, name, desc, dry_run=False):
    ids = models.execute_kw(
        db, uid, password,
        'ir.module.module', 'search',
        [[['name', '=', name]]]
    )
    if not ids:
        print(f"  MISSING  {name:<40} {desc}")
        return "missing"

    info = models.execute_kw(
        db, uid, password,
        'ir.module.module', 'read',
        [ids[0]], {'fields': ['state', 'shortdesc']}
    )
    if isinstance(info, list):
        info = info[0]
    state = info['state']

    if state == 'installed':
        print(f"  OK       {name:<40} (already installed)")
        return "installed"

    if dry_run:
        print(f"  PENDING  {name:<40} {desc} [{state}]")
        return "pending"

    print(f"  INSTALL  {name:<40} {desc}...")
    for attempt in range(1, MODULE_INSTALL_RETRIES + 1):
        try:
            models.execute_kw(
                db, uid, password,
                'ir.module.module', 'button_immediate_install',
                [[ids[0]]]
            )
            print(f"           {name:<40} installed!")
            return "installed"
        except Exception as e:
            err = str(e).lower()
            is_cron_lock = (
                "planerad åtgärd" in err
                or "scheduled action" in err
                or "module operations are not possible" in err
            )
            if is_cron_lock and attempt < MODULE_INSTALL_RETRIES:
                print(
                    f"  WAIT     {name:<40} "
                    f"cron lock, retry {attempt}/{MODULE_INSTALL_RETRIES} "
                    f"in {MODULE_INSTALL_RETRY_WAIT}s"
                )
                time.sleep(MODULE_INSTALL_RETRY_WAIT)
                continue
            print(f"  ERROR    {name:<40} {e}")
            return "error"


def run_batch(models, uid, db, password, label, modules, dry_run):
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    stats = {"installed": 0, "pending": 0, "missing": 0, "error": 0}
    for name, desc in modules:
        result = install_module(models, uid, db, password, name, desc, dry_run)
        stats[result] += 1
        if result == "installed" and not dry_run:
            time.sleep(1)  # breathe between installs

    return stats


def main():
    args = parse_args()
    uid, models = connect(args.url, args.db, args.user, args.password)
    update_module_list(models, uid, args.db, args.password)

    paused_cron_ids = []
    if args.pause_cron and not args.dry_run:
        paused_cron_ids = pause_scheduled_actions(
            models, uid, args.db, args.password, wait_seconds=args.cron_wait
        )

    try:
        total = {"installed": 0, "pending": 0, "missing": 0, "error": 0}

        if not args.skip_core:
            s = run_batch(models, uid, args.db, args.password,
                          "ODOO CORE MODULES", CORE_MODULES, args.dry_run)
            for k in total:
                total[k] += s[k]

        if not args.skip_oca:
            s = run_batch(models, uid, args.db, args.password,
                          "OCA COMMUNITY MODULES", OCA_MODULES, args.dry_run)
            for k in total:
                total[k] += s[k]

        # ── Summary ──
        print(f"\n{'='*70}")
        print("  SUMMARY")
        print(f"{'='*70}")
        print(f"  Installed / OK : {total['installed']}")
        print(f"  Pending        : {total['pending']}")
        print(f"  Missing        : {total['missing']}")
        print(f"  Errors         : {total['error']}")
        print(f"{'='*70}")

        if total['missing']:
            print("\nMissing modules are likely not in addons_path.")
            print("Rebuild the Docker image and restart the container,")
            print("then run this script again.")

        if total['error']:
            print("\nSome modules had errors. Check logs and retry.")

        if not total['missing'] and not total['error']:
            print("\nAll modules installed successfully!")
            print("All departments are ready to use in Odoo.")
    finally:
        if paused_cron_ids:
            resume_scheduled_actions(models, uid, args.db, args.password, paused_cron_ids)


if __name__ == "__main__":
    raise SystemExit(main() or 0)
