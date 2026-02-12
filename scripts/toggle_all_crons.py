#!/usr/bin/env python3
"""
Pause/resume Odoo scheduled actions (ir.cron) over XML-RPC.

Typical flow:
  1) python scripts/toggle_all_crons.py pause --wait 60 --timeout 900
  2) Upgrade modules in Odoo UI (or CLI)
  3) python scripts/toggle_all_crons.py resume
"""

import argparse
import json
import os
import sys
import time
import xmlrpc.client


DEFAULT_URL = "https://snushallen.cloud"
DEFAULT_DB = "odoo"
DEFAULT_USER = "mikael@snussidan.se"
DEFAULT_PASSWORD = "a04315610102c5d4cde37f7c8afea09d8721569a"  # API key
DEFAULT_STATE_FILE = ".cron_pause_state.json"

TOGGLE_RETRIES = 4
TOGGLE_RETRY_WAIT = 5


def parse_args():
    parser = argparse.ArgumentParser(description="Pause/resume Odoo scheduled actions")
    parser.add_argument("action", choices=["pause", "resume", "status"])
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--wait", type=int, default=60, help="Wait after pause (seconds)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Max seconds to retry locked scheduled actions",
    )
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE)
    parser.add_argument(
        "--no-fetchmail",
        action="store_true",
        help="Do not toggle incoming mail servers (fetchmail.server)",
    )
    return parser.parse_args()


def connect(url, db, user, password):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise RuntimeError("Authentication failed")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models


def is_lock_error(exc):
    err = str(exc).lower()
    return (
        "currently executing" in err
        or "cannot be modified" in err
        or "kan inte andras" in err
        or "kan inte andras just nu" in err
        or "could not obtain lock on row in relation \"ir_cron\"" in err
        or "locknotavailable" in err
    )


def write_state(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def read_state(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def toggle_records(models, uid, db, password, model, ids, target_active):
    toggled = []
    locked = []
    for rec_id in ids:
        done = False
        for attempt in range(1, TOGGLE_RETRIES + 1):
            try:
                models.execute_kw(
                    db,
                    uid,
                    password,
                    model,
                    "write",
                    [[rec_id], {"active": target_active}],
                )
                toggled.append(rec_id)
                done = True
                break
            except Exception as exc:  # noqa: BLE001
                if is_lock_error(exc) and attempt < TOGGLE_RETRIES:
                    time.sleep(TOGGLE_RETRY_WAIT)
                    continue
                break
        if not done:
            locked.append(rec_id)
    return toggled, locked


def pause_all(args, uid, models):
    active_crons = models.execute_kw(
        args.db,
        uid,
        args.password,
        "ir.cron",
        "search_read",
        [[["active", "=", True]]],
        {"fields": ["id", "name"], "order": "id asc"},
    )
    cron_ids = [rec["id"] for rec in active_crons]
    if not cron_ids:
        print("No active scheduled actions found.")
        return 0

    paused = set()
    locked = list(cron_ids)
    deadline = time.time() + max(0, args.timeout)

    while locked and time.time() < deadline:
        toggled, still_locked = toggle_records(
            models, uid, args.db, args.password, "ir.cron", locked, False
        )
        paused.update(toggled)
        locked = still_locked
        if locked and time.time() < deadline:
            retry_sleep = min(
                max(1, TOGGLE_RETRY_WAIT * 2),
                max(1, int(deadline - time.time())),
            )
            print(
                f"{len(locked)} scheduled actions still locked/running. "
                f"Retrying in {retry_sleep}s..."
            )
            time.sleep(retry_sleep)

    paused_fetchmail_ids = []
    fetchmail_locked = []
    if not args.no_fetchmail:
        fetchmail_ids = models.execute_kw(
            args.db,
            uid,
            args.password,
            "fetchmail.server",
            "search",
            [[["active", "=", True]]],
        )
        if fetchmail_ids:
            paused_fetchmail_ids, fetchmail_locked = toggle_records(
                models,
                uid,
                args.db,
                args.password,
                "fetchmail.server",
                fetchmail_ids,
                False,
            )

    payload = {
        "url": args.url,
        "db": args.db,
        "paused_cron_ids": sorted(paused),
        "locked_cron_ids": locked,
        "paused_fetchmail_ids": sorted(paused_fetchmail_ids),
        "locked_fetchmail_ids": fetchmail_locked,
        "created_at_epoch": int(time.time()),
    }
    write_state(args.state_file, payload)

    print(f"Paused scheduled actions: {len(paused)}")
    if locked:
        print(
            f"Could not pause {len(locked)} scheduled actions within timeout "
            f"({args.timeout}s)."
        )
    if not args.no_fetchmail:
        print(f"Paused incoming mail servers: {len(paused_fetchmail_ids)}")
        if fetchmail_locked:
            print(f"Could not pause {len(fetchmail_locked)} incoming mail servers.")

    if args.wait > 0:
        print(f"Waiting {args.wait}s for running transactions to finish...")
        time.sleep(args.wait)
    print(f"State file written: {args.state_file}")
    return 1 if locked else 0


def resume_all(args, uid, models):
    state = read_state(args.state_file)
    cron_ids = state.get("paused_cron_ids", [])
    fetchmail_ids = state.get("paused_fetchmail_ids", [])
    if not cron_ids and (args.no_fetchmail or not fetchmail_ids):
        print(f"No paused IDs found in state file: {args.state_file}")
        return 0

    resumed, resume_locked = toggle_records(
        models, uid, args.db, args.password, "ir.cron", cron_ids, True
    )
    print(f"Resumed scheduled actions: {len(resumed)}")
    if resume_locked:
        print(f"Could not resume {len(resume_locked)} scheduled actions.")

    fetchmail_locked = []
    if not args.no_fetchmail and fetchmail_ids:
        resumed_fetchmail, fetchmail_locked = toggle_records(
            models,
            uid,
            args.db,
            args.password,
            "fetchmail.server",
            fetchmail_ids,
            True,
        )
        print(f"Resumed incoming mail servers: {len(resumed_fetchmail)}")
        if fetchmail_locked:
            print(f"Could not resume {len(fetchmail_locked)} incoming mail servers.")

    # Keep the state file if there are unresolved locks.
    unresolved = bool(resume_locked or fetchmail_locked)
    if not unresolved and os.path.exists(args.state_file):
        os.remove(args.state_file)
        print(f"Removed state file: {args.state_file}")

    return 1 if unresolved else 0


def show_status(args, uid, models):
    active_count = models.execute_kw(
        args.db,
        uid,
        args.password,
        "ir.cron",
        "search_count",
        [[["active", "=", True]]],
    )
    inactive_count = models.execute_kw(
        args.db,
        uid,
        args.password,
        "ir.cron",
        "search_count",
        [[["active", "=", False]]],
    )
    print(f"Scheduled actions: active={active_count}, inactive={inactive_count}")

    if not args.no_fetchmail:
        fm_active = models.execute_kw(
            args.db,
            uid,
            args.password,
            "fetchmail.server",
            "search_count",
            [[["active", "=", True]]],
        )
        fm_inactive = models.execute_kw(
            args.db,
            uid,
            args.password,
            "fetchmail.server",
            "search_count",
            [[["active", "=", False]]],
        )
        print(f"Incoming mail servers: active={fm_active}, inactive={fm_inactive}")
    return 0


def main():
    args = parse_args()
    try:
        uid, models = connect(args.url, args.db, args.user, args.password)
    except Exception as exc:  # noqa: BLE001
        print(f"Connection/authentication failed: {exc}")
        return 1

    print(f"Connected to {args.url} (db={args.db}, uid={uid})")
    if args.action == "pause":
        return pause_all(args, uid, models)
    if args.action == "resume":
        return resume_all(args, uid, models)
    return show_status(args, uid, models)


if __name__ == "__main__":
    raise SystemExit(main())
