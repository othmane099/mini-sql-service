"""create query_history table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-12 00:02:00

"""
import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "query_history",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("connection_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum("generate", "execute", name="queryeventtype"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_query_history_connection_id", "query_history", ["connection_id"])


def downgrade() -> None:
    op.drop_index("ix_query_history_connection_id", table_name="query_history")
    op.drop_table("query_history")
    op.execute("DROP TYPE IF EXISTS queryeventtype")
