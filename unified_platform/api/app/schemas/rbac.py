from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import ORMModel


class RoleResponse(ORMModel):
    id: int
    key: str
    name: str


class PermissionResponse(ORMModel):
    id: int
    key: str
    name: str


class UpdateUserRolesRequest(BaseModel):
    role_ids: list[int]


class UpdateUserLocationScopesRequest(BaseModel):
    location_ids: list[int]
