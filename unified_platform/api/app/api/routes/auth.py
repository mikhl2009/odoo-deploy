from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.models.core import CoreUser
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserMeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(CoreUser).where(CoreUser.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")

    user.last_login_at = datetime.now(UTC)
    db.add(user)
    db.commit()

    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest) -> TokenResponse:
    try:
        decoded = decode_refresh_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise ValueError("Invalid token type")
        user_id = decoded["sub"]
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    return TokenResponse(access_token=create_access_token(str(user_id)), refresh_token=create_refresh_token(str(user_id)))


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"message": "Logged out"}


@router.get("/me", response_model=UserMeResponse)
def me(current_user: CoreUser = Depends(get_current_user)) -> UserMeResponse:
    return UserMeResponse.model_validate(current_user)
