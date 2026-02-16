"""Initial migration helper from Odoo into Unified ERP (Phase 1 baseline)."""

from __future__ import annotations

import os
import xmlrpc.client

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.mdm import MdmPartner
from app.models.pim import PimProduct, PimProductI18n


def odoo_session():
    url = os.getenv("ODOO_URL", "")
    db = os.getenv("ODOO_DB", "")
    username = os.getenv("ODOO_USER", "")
    password = os.getenv("ODOO_PASSWORD", "")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise RuntimeError("Cannot authenticate against Odoo")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return db, uid, password, models


def migrate_suppliers(session: Session, db_name: str, uid: int, password: str, models) -> int:
    suppliers = models.execute_kw(
        db_name,
        uid,
        password,
        "res.partner",
        "search_read",
        [[["supplier_rank", ">", 0]]],
        {"fields": ["name", "email", "phone", "vat"]},
    )
    count = 0
    for supplier in suppliers:
        existing = session.query(MdmPartner).filter(MdmPartner.legal_name == supplier["name"]).first()
        if existing:
            continue
        session.add(
            MdmPartner(
                partner_type="supplier",
                legal_name=supplier["name"],
                email=supplier.get("email"),
                phone=supplier.get("phone"),
                vat_no=supplier.get("vat"),
                active=True,
            )
        )
        count += 1
    return count


def migrate_products(session: Session, company_id: int, db_name: str, uid: int, password: str, models) -> int:
    products = models.execute_kw(
        db_name,
        uid,
        password,
        "product.template",
        "search_read",
        [[["active", "=", True], ["default_code", "!=", False]]],
        {"fields": ["default_code", "barcode", "name"]},
    )
    count = 0
    for row in products:
        existing = session.query(PimProduct).filter(PimProduct.company_id == company_id, PimProduct.sku == row["default_code"]).first()
        if existing:
            continue
        product = PimProduct(
            company_id=company_id,
            sku=row["default_code"],
            ean=row.get("barcode"),
            status="active",
            product_type="simple",
            is_tobacco=True,
        )
        session.add(product)
        session.flush()
        session.add(PimProductI18n(product_id=product.id, language_code="en", name=row.get("name") or row["default_code"]))
        count += 1
    return count


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    company_id = int(os.getenv("DEFAULT_COMPANY_ID", "1"))
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    db_name, uid, password, models = odoo_session()
    engine = create_engine(database_url, future=True)
    with Session(engine) as session:
        suppliers = migrate_suppliers(session, db_name, uid, password, models)
        products = migrate_products(session, company_id, db_name, uid, password, models)
        session.commit()
    print(f"Migrated suppliers={suppliers}, products={products}")


if __name__ == "__main__":
    main()
