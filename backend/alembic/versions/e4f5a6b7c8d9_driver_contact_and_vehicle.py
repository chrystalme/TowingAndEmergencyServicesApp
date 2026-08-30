"""Driver contact number and assigned tow vehicle.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing drivers have no number yet, so this has to be nullable at first;
    # backfilled to "" and made NOT NULL so the application never has to
    # distinguish "no number" from NULL.
    op.add_column("drivers", sa.Column("phone_number", sa.String(), nullable=True))
    op.execute("UPDATE drivers SET phone_number = '' WHERE phone_number IS NULL")
    op.alter_column(
        "drivers", "phone_number", nullable=False, server_default=""
    )
    op.add_column("drivers", sa.Column("vehicle_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_drivers_vehicle_id", "drivers", "vehicles", ["vehicle_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_drivers_vehicle_id", "drivers", type_="foreignkey")
    op.drop_column("drivers", "vehicle_id")
    op.drop_column("drivers", "phone_number")
