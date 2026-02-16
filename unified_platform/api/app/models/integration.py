from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IntOutboxEvent(Base):
    __tablename__ = "int_outbox_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


class IntStoreChannel(Base):
    __tablename__ = "int_store_channel"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_int_store_channel_company_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("core_company.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntStoreConnection(Base):
    __tablename__ = "int_store_connection"
    __table_args__ = (UniqueConstraint("store_channel_id", "provider", name="uq_int_store_connection_provider"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_channel_id: Mapped[int] = mapped_column(ForeignKey("int_store_channel.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    api_base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    consumer_key: Mapped[str] = mapped_column(String(255), nullable=False)
    consumer_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    webhook_secret: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntExternalIdMap(Base):
    __tablename__ = "int_external_id_map"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_entity",
            "source_id",
            "target_entity",
            name="uq_int_external_id_map_unique",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_entity: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntSyncJob(Base):
    __tablename__ = "int_sync_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_connection_id: Mapped[int] = mapped_column(ForeignKey("int_store_connection.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    started_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    summary_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntSyncQueue(Base):
    __tablename__ = "int_sync_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("int_sync_job.id"))
    store_connection_id: Mapped[int | None] = mapped_column(ForeignKey("int_store_connection.id"))
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


class IntSyncError(Base):
    __tablename__ = "int_sync_error"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("int_sync_job.id"))
    queue_id: Mapped[int | None] = mapped_column(ForeignKey("int_sync_queue.id"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IntWebhookEvent(Base):
    __tablename__ = "int_webhook_event"
    __table_args__ = (UniqueConstraint("provider", "external_event_id", name="uq_int_webhook_provider_event"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_connection_id: Mapped[int | None] = mapped_column(ForeignKey("int_store_connection.id"))
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="received", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))


class IntStoreProductSetting(Base):
    __tablename__ = "int_store_product_setting"
    __table_args__ = (
        UniqueConstraint("store_connection_id", "variant_id", name="uq_int_store_product_setting_connection_variant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_connection_id: Mapped[int] = mapped_column(ForeignKey("int_store_connection.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(ForeignKey("pim_product_variant.id"), nullable=False)
    web_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_push_at: Mapped[str | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
