from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.core import (
    CoreCompany,
    CoreLocation,
    CorePermission,
    CoreRole,
    CoreRolePermission,
    CoreUser,
    CoreUserRole,
)
from app.models.pim import PimPriceList


DEFAULT_PERMISSIONS = [
    "pim.read",
    "pim.write",
    "inventory.read",
    "inventory.write",
    "purchase.read",
    "purchase.write",
    "sales.read",
    "sales.write",
    "sync.read",
    "sync.write",
    "dashboard.read",
    "rbac.read",
    "rbac.write",
]


def seed_defaults(db: Session) -> None:
    company = db.scalar(select(CoreCompany).where(CoreCompany.legal_name == "Unified Demo AB"))
    if not company:
        company = CoreCompany(
            legal_name="Unified Demo AB",
            org_no="556000-0000",
            vat_no="SE556000000001",
            currency_code="SEK",
            timezone="Europe/Stockholm",
            country_code="SE",
            active=True,
        )
        db.add(company)
        db.flush()

    location = db.scalar(select(CoreLocation).where(CoreLocation.company_id == company.id, CoreLocation.code == "WH-001"))
    if not location:
        db.add(
            CoreLocation(
                company_id=company.id,
                code="WH-001",
                name="Central Warehouse",
                location_type="warehouse",
                active=True,
            )
        )

    permissions = {}
    for perm_key in DEFAULT_PERMISSIONS:
        permission = db.scalar(select(CorePermission).where(CorePermission.key == perm_key))
        if not permission:
            permission = CorePermission(key=perm_key, name=perm_key)
            db.add(permission)
            db.flush()
        permissions[perm_key] = permission

    admin_role = db.scalar(select(CoreRole).where(CoreRole.key == "admin"))
    if not admin_role:
        admin_role = CoreRole(key="admin", name="Admin")
        db.add(admin_role)
        db.flush()

    for permission in permissions.values():
        exists = db.scalar(
            select(CoreRolePermission).where(
                CoreRolePermission.role_id == admin_role.id,
                CoreRolePermission.permission_id == permission.id,
            )
        )
        if not exists:
            db.add(CoreRolePermission(role_id=admin_role.id, permission_id=permission.id))

    admin_user = db.scalar(select(CoreUser).where(CoreUser.email == "admin@unified.local"))
    if not admin_user:
        admin_user = CoreUser(email="admin@unified.local", password_hash=hash_password("admin123"), status="active")
        db.add(admin_user)
        db.flush()

    admin_role_binding = db.scalar(
        select(CoreUserRole).where(CoreUserRole.user_id == admin_user.id, CoreUserRole.role_id == admin_role.id)
    )
    if not admin_role_binding:
        db.add(CoreUserRole(user_id=admin_user.id, role_id=admin_role.id))

    default_price_list = db.scalar(
        select(PimPriceList).where(PimPriceList.company_id == company.id, PimPriceList.name == "Default Retail SEK")
    )
    if not default_price_list:
        db.add(
            PimPriceList(
                company_id=company.id,
                name="Default Retail SEK",
                channel_type="retail",
                currency_code="SEK",
                active=True,
            )
        )

    db.commit()
