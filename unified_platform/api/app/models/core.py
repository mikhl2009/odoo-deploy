from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class CoreCompany(Base, TimestampMixin):
    __tablename__ = "core_company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_no: Mapped[str | None] = mapped_column(String(64))
    vat_no: Mapped[str | None] = mapped_column(String(64))
    currency_code: Mapped[str] = mapped_column(String(3), default="SEK", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Stockholm", nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), default="SE", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    locations: Mapped[list["CoreLocation"]] = relationship(back_populates="company")


class CoreLocation(Base, TimestampMixin):
    __tablename__ = "core_location"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_core_location_company_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_type: Mapped[str] = mapped_column(String(32), nullable=False)
    parent_location_id: Mapped[int | None] = mapped_column(ForeignKey("core_location.id"))
    address: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[CoreCompany] = relationship(back_populates="locations")


class CoreUser(Base, TimestampMixin):
    __tablename__ = "core_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    roles: Mapped[list["CoreUserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    location_scopes: Mapped[list["CoreUserLocationScope"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class CoreRole(Base):
    __tablename__ = "core_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    permissions: Mapped[list["CoreRolePermission"]] = relationship(back_populates="role", cascade="all, delete-orphan")


class CorePermission(Base):
    __tablename__ = "core_permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)


class CoreRolePermission(Base):
    __tablename__ = "core_role_permission"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_core_role_permission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("core_role.id"), nullable=False)
    permission_id: Mapped[int] = mapped_column(ForeignKey("core_permission.id"), nullable=False)

    role: Mapped[CoreRole] = relationship(back_populates="permissions")
    permission: Mapped[CorePermission] = relationship()


class CoreUserRole(Base):
    __tablename__ = "core_user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_core_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("core_user.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("core_role.id"), nullable=False)

    user: Mapped[CoreUser] = relationship(back_populates="roles")
    role: Mapped[CoreRole] = relationship()


class CoreUserLocationScope(Base):
    __tablename__ = "core_user_location_scope"
    __table_args__ = (UniqueConstraint("user_id", "location_id", name="uq_core_user_location_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("core_user.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("core_location.id"), nullable=False)

    user: Mapped[CoreUser] = relationship(back_populates="location_scopes")
    location: Mapped[CoreLocation] = relationship()


class CoreAuditEvent(Base):
    __tablename__ = "core_audit_event"
    __table_args__ = (
        Index("ix_core_audit_event_entity", "entity_type", "entity_id"),
        Index("ix_core_audit_event_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("core_user.id"))
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    before_jsonb: Mapped[dict | None] = mapped_column(JSON)
    after_jsonb: Mapped[dict | None] = mapped_column(JSON)
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
