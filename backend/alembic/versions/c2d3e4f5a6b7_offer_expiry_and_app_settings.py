"""Offer expiry bookkeeping and runtime-changeable settings.

Adds:
  * dispatches.expires_at      - when an unanswered offer lapses
  * dispatches.extension_count - how many times the driver bought more time
  * app_settings               - operational knobs changeable without a deploy

Revision ID: c2d3e4f5a6b7
Revises: a1f2c3d4e5f6
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "a1f2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("dispatches", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column(
        "dispatches",
        sa.Column("extension_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # The expiry sweep filters on (status, expires_at) on every match and job
    # list, so give it an index rather than a scan of every dispatch ever made.
    op.create_index(
        "ix_dispatches_status_expires_at",
        "dispatches",
        ["status", "expires_at"],
        unique=False,
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index("ix_dispatches_status_expires_at", table_name="dispatches")
    op.drop_column("dispatches", "extension_count")
    op.drop_column("dispatches", "expires_at")
