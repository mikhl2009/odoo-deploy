from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import (
    CoreLocation,
    CorePermission,
    CoreRole,
    CoreUser,
    CoreUserLocationScope,
    CoreUserRole,
)
from app.schemas.common import MessageResponse
from app.schemas.rbac import (
    PermissionResponse,
    RoleResponse,
    UpdateUserLocationScopesRequest,
    UpdateUserRolesRequest,
)

router = APIRouter(prefix="/rbac", tags=["rbac"])


@router.get("/roles", response_model=list[RoleResponse])
def roles(_: CoreUser = Depends(require_permission("rbac.read")), db: Session = Depends(get_db)) -> list[CoreRole]:
    return db.scalars(select(CoreRole).order_by(CoreRole.key)).all()


@router.get("/permissions", response_model=list[PermissionResponse])
def permissions(_: CoreUser = Depends(require_permission("rbac.read")), db: Session = Depends(get_db)) -> list[CorePermission]:
    return db.scalars(select(CorePermission).order_by(CorePermission.key)).all()


@router.patch("/users/{user_id}/roles", response_model=MessageResponse)
def patch_user_roles(
    user_id: int,
    payload: UpdateUserRolesRequest,
    _: CoreUser = Depends(require_permission("rbac.write")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = db.get(CoreUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.execute(delete(CoreUserRole).where(CoreUserRole.user_id == user_id))
    for role_id in payload.role_ids:
        if not db.get(CoreRole, role_id):
            raise HTTPException(status_code=400, detail=f"Role {role_id} not found")
        db.add(CoreUserRole(user_id=user_id, role_id=role_id))
    db.commit()
    return MessageResponse(message="User roles updated")


@router.patch("/users/{user_id}/location-scopes", response_model=MessageResponse)
def patch_user_location_scopes(
    user_id: int,
    payload: UpdateUserLocationScopesRequest,
    _: CoreUser = Depends(require_permission("rbac.write")),
    db: Session = Depends(get_db),
) -> MessageResponse:
    user = db.get(CoreUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.execute(delete(CoreUserLocationScope).where(CoreUserLocationScope.user_id == user_id))
    for location_id in payload.location_ids:
        if not db.get(CoreLocation, location_id):
            raise HTTPException(status_code=400, detail=f"Location {location_id} not found")
        db.add(CoreUserLocationScope(user_id=user_id, location_id=location_id))
    db.commit()
    return MessageResponse(message="User location scopes updated")
