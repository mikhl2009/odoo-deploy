from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.core import CorePermission, CoreRolePermission, CoreUser, CoreUserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> CoreUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = int(payload.get("sub", "0"))
    except Exception:
        raise credentials_exception

    user = db.get(CoreUser, user_id)
    if not user:
        raise credentials_exception
    return user


def require_permission(permission_key: str):
    def checker(
        current_user: CoreUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CoreUser:
        stmt = (
            select(CorePermission.key)
            .join(CoreRolePermission, CoreRolePermission.permission_id == CorePermission.id)
            .join(CoreUserRole, CoreUserRole.role_id == CoreRolePermission.role_id)
            .where(CoreUserRole.user_id == current_user.id)
        )
        permissions = set(db.scalars(stmt).all())
        if permission_key not in permissions and "rbac.write" not in permissions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission_key}")
        return current_user

    return checker
