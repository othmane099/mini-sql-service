"""add explain to queryeventtype

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-06-12 00:03:00

"""
from alembic import op

revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE queryeventtype ADD VALUE IF NOT EXISTS 'explain'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; a full recreate would be required
    pass
