from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.core import (
    CoreCompany,
    CoreLocation,
    CorePermission,
    CoreRole,
    CoreRolePermission,
    CoreUser,
    CoreUserRole,
)
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserMeResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

_ALL_PERMISSIONS = [
    "sync.read", "sync.write",
    "pim.read", "pim.write",
    "inventory.read", "inventory.write",
    "sales.read", "sales.write",
    "purchase.read", "purchase.write",
    "reports.read",
    "admin",
]


def _authenticate(email: str, password: str, db: Session) -> TokenResponse:
    user = db.scalar(select(CoreUser).where(CoreUser.email == email))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    user.last_login_at = datetime.now(UTC)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


# ---------------------------------------------------------------------------
# JSON login  (used by the actual frontend / scripts)
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return _authenticate(payload.email, payload.password, db)


# ---------------------------------------------------------------------------
# OAuth2 form login  (used by Swagger UI "Authorize" button)
# username = e-mail address
# ---------------------------------------------------------------------------

@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password flow endpoint — Swagger UI Authorize dialog uses this."""
    return _authenticate(form.username, form.password, db)


# ---------------------------------------------------------------------------
# First-run setup  (only works when no users exist yet)
# ---------------------------------------------------------------------------

@router.post("/setup", summary="First-run: create admin user (only when DB is empty)")
def setup(db: Session = Depends(get_db)) -> dict:
    """
    Creates:
      - CoreCompany  id=1  'Snushallen i Norden AB'
      - CoreLocation id=1  'Huvudlager'  (type=warehouse)
      - CoreRole     key=admin  with all permissions
      - CoreUser     admin@snushallen.cloud  password=Admin1234!

    Returns 409 if any user already exists.
    """
    existing_users = db.scalars(select(CoreUser).order_by(CoreUser.id)).all()
    if existing_users:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"{len(existing_users)} user(s) already exist. Use /auth/login.",
                "emails": [u.email for u in existing_users],
                "hint": "POST /api/v1/auth/admin-reset to force-reset the admin password.",
            },
        )

    # ── Company ──────────────────────────────────────────────────────────
    company = db.scalar(select(CoreCompany).limit(1))
    if not company:
        company = CoreCompany(
            legal_name="Snushallen i Norden AB",
            org_no="559012-3456",
            currency_code="SEK",
            timezone="Europe/Stockholm",
            country_code="SE",
        )
        db.add(company)
        db.flush()

    # ── Location ─────────────────────────────────────────────────────────
    location = db.scalar(select(CoreLocation).limit(1))
    if not location:
        location = CoreLocation(
            company_id=company.id,
            code="HL",
            name="Huvudlager",
            location_type="warehouse",
        )
        db.add(location)
        db.flush()

    # ── Role + permissions ────────────────────────────────────────────────
    role = db.scalar(select(CoreRole).where(CoreRole.key == "admin"))
    if not role:
        role = CoreRole(key="admin", name="Administrator")
        db.add(role)
        db.flush()

        for perm_key in _ALL_PERMISSIONS:
            perm = db.scalar(select(CorePermission).where(CorePermission.key == perm_key))
            if not perm:
                perm = CorePermission(key=perm_key, name=perm_key.replace(".", " ").title())
                db.add(perm)
                db.flush()
            db.add(CoreRolePermission(role_id=role.id, permission_id=perm.id))

    # ── Admin user ────────────────────────────────────────────────────────
    default_password = "Admin1234!"
    user = CoreUser(
        email="admin@snushallen.cloud",
        password_hash=hash_password(default_password),
        status="active",
    )
    db.add(user)
    db.flush()
    db.add(CoreUserRole(user_id=user.id, role_id=role.id))
    db.commit()

    return {
        "message": "Setup complete. Change the password immediately.",
        "email": user.email,
        "password": default_password,
        "company_id": company.id,
        "location_id": location.id,
    }


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


# ---------------------------------------------------------------------------
# Emergency admin password reset (proof-of-server: requires JWT_SECRET_KEY)
# ---------------------------------------------------------------------------

@router.post(
    "/admin-reset",
    summary="Emergency: reset admin password using server secret",
)
def admin_reset(
    server_secret: str,
    new_password: str = "Admin1234!",
    db: Session = Depends(get_db),
) -> dict:
    """
    Resets the first admin user's password without needing to log in.
    Requires `server_secret` = the JWT_SECRET_KEY env var value.
    Only useful for initial setup / locked-out scenarios.
    """
    from app.core.config import settings as cfg  # avoid circular at module level

    if server_secret != cfg.jwt_secret_key:
        raise HTTPException(status_code=403, detail="Invalid server secret")

    user = db.scalar(select(CoreUser).order_by(CoreUser.id).limit(1))
    if not user:
        raise HTTPException(status_code=404, detail="No users in database – call /auth/setup first")

    user.password_hash = hash_password(new_password)
    user.status = "active"
    db.commit()

    return {
        "message": "Password reset successfully.",
        "email": user.email,
        "new_password": new_password,
    }
