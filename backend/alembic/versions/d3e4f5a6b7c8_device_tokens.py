"""Device push tokens.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False, server_default="android"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_tokens_id"), "device_tokens", ["id"], unique=False)
    # Every push looks up a user's tokens, so index the lookup.
    op.create_index(
        op.f("ix_device_tokens_user_id"), "device_tokens", ["user_id"], unique=False
    )
    # A token identifies one install; re-registering must update, not duplicate.
    op.create_index(
        "uq_device_tokens_token", "device_tokens", ["token"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_device_tokens_token", table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_user_id"), table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_id"), table_name="device_tokens")
    op.drop_table("device_tokens")
