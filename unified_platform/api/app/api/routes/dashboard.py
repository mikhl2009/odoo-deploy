from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.schemas.dashboard import DashboardKpiResponse
from app.services.dashboard import get_dashboard_kpis

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=DashboardKpiResponse)
def dashboard_kpis(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("dashboard.read")),
) -> DashboardKpiResponse:
    return get_dashboard_kpis(db)
