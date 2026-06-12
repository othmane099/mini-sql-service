"""create connections table

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-12 00:01:00

"""
import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "db_type",
            sa.Enum("postgresql", name="dbtype"),
            nullable=False,
        ),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password", sa.String(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_connections_name", "connections", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_connections_name", table_name="connections")
    op.drop_table("connections")
    op.execute("DROP TYPE IF EXISTS dbtype")
