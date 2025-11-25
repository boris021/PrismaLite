"""create events table

Revision ID: 0001_create_events
Revises:
Create Date: 2025-11-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_create_events"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("pos_id", sa.String(length=32), nullable=False),
        sa.Column("cashier", sa.String(length=64)),
        sa.Column("event_code", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_events_tenant", "events", ["tenant_id"])
    op.create_index("idx_events_store", "events", ["store_id"])
    op.create_index("idx_events_event_code", "events", ["event_code"])


def downgrade() -> None:
    op.drop_index("idx_events_event_code", table_name="events")
    op.drop_index("idx_events_store", table_name="events")
    op.drop_index("idx_events_tenant", table_name="events")
    op.drop_table("events")

