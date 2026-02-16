"""Odoo coexistence adapter (Phase 1 baseline).

Reads pending outbox events and posts selected payloads into Odoo through XML-RPC.
"""

from __future__ import annotations

import os
import xmlrpc.client

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.integration import IntOutboxEvent


def odoo_connect():
    url = os.getenv("ODOO_URL", "")
    db = os.getenv("ODOO_DB", "")
    username = os.getenv("ODOO_USER", "")
    password = os.getenv("ODOO_PASSWORD", "")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise RuntimeError("Odoo authentication failed")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return db, uid, password, models


def push_product_event(models, db_name: str, uid: int, password: str, payload: dict) -> None:
    # This creates a lightweight sync log on Odoo side; full mapping can extend here.
    models.execute_kw(
        db_name,
        uid,
        password,
        "mail.message",
        "create",
        [[{"body": f"Unified ERP product sync: {payload}"}]],
    )


def process_outbox(database_url: str) -> int:
    db_name, uid, password, odoo_models = odoo_connect()
    engine = create_engine(database_url, future=True)
    processed = 0
    with Session(engine) as session:
        events = session.scalars(
            select(IntOutboxEvent).where(IntOutboxEvent.status == "pending").order_by(IntOutboxEvent.id).limit(100)
        ).all()
        for event in events:
            try:
                if event.event_name == "product.updated":
                    push_product_event(odoo_models, db_name, uid, password, event.payload)
                event.status = "processed"
                processed += 1
            except Exception as exc:
                event.status = "failed"
                event.error_message = str(exc)
        session.commit()
    return processed


if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL required")
    count = process_outbox(database_url)
    print(f"Processed {count} outbox events")
