"""phase2 sales and woo sync schema

Revision ID: 20260216_0002
Revises: 20260216_0001
Create Date: 2026-02-16
"""

from __future__ import annotations

from alembic import op

from app.db.base import Base
from app.models import core, integration, inventory, mdm, pim, procurement, sales  # noqa: F401

revision = "20260216_0002"
down_revision = "20260216_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
