from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import audit, auth, dashboard, inbound, integration, inventory, products, purchase, rbac, suppliers

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(rbac.router)
api_router.include_router(audit.router)
api_router.include_router(products.router)
api_router.include_router(suppliers.router)
api_router.include_router(purchase.router)
api_router.include_router(inbound.router)
api_router.include_router(inventory.router)
api_router.include_router(dashboard.router)
api_router.include_router(integration.router)
