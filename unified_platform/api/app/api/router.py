from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    audit,
    auth,
    dashboard,
    dev,
    inbound,
    integration,
    inventory,
    nshift,
    pim_import,
    products,
    purchase,
    rbac,
    sales,
    suppliers,
    wgr,
    woo,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(rbac.router)
api_router.include_router(audit.router)
api_router.include_router(products.router)
api_router.include_router(suppliers.router)
api_router.include_router(purchase.router)
api_router.include_router(inbound.router)
api_router.include_router(inventory.router)
api_router.include_router(sales.router)
api_router.include_router(dashboard.router)
api_router.include_router(integration.router)
api_router.include_router(woo.router)
api_router.include_router(wgr.router)
api_router.include_router(nshift.router)
api_router.include_router(pim_import.router)
api_router.include_router(dev.router)
