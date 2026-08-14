"""add dispatch/routing schema

Revision ID: a1f2c3d4e5f6
Revises: b810db1731f7
Create Date: 2026-08-14 00:00:00.000000

Adds: users.role, ServiceRequest dispatch fields + coords, the drivers live
profile table, and the dispatches assignment table.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f2c3d4e5f6'
down_revision = 'b810db1731f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users gain a role (commuter|driver|company|admin).
    op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='commuter'))

    # Service requests gain dispatch-relevant fields + coordinates.
    op.add_column('service_requests', sa.Column('service_type', sa.String(), nullable=False, server_default='towing'))
    op.add_column('service_requests', sa.Column('vehicle_type', sa.String(), nullable=False, server_default='car'))
    op.add_column('service_requests', sa.Column('name', sa.String(), nullable=False, server_default=''))
    op.add_column('service_requests', sa.Column('phone_number', sa.String(), nullable=False, server_default=''))
    op.add_column('service_requests', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('service_requests', sa.Column('longitude', sa.Float(), nullable=True))

    # Driver live profile (availability + position).
    op.create_table('drivers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('is_online', sa.Boolean(), nullable=False),
        sa.Column('current_status', sa.String(), nullable=False),
        sa.Column('current_lat', sa.Float(), nullable=True),
        sa.Column('current_lng', sa.Float(), nullable=True),
        sa.Column('last_position_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index(op.f('ix_drivers_id'), 'drivers', ['id'], unique=False)

    # Dispatch assignments (matched driver <-> request).
    op.create_table('dispatches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('distance_km', sa.Float(), nullable=True),
        sa.Column('eta_minutes', sa.Float(), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['request_id'], ['service_requests.id'], ),
        sa.ForeignKeyConstraint(['driver_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_dispatches_id'), 'dispatches', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dispatches_id'), table_name='dispatches')
    op.drop_table('dispatches')
    op.drop_index(op.f('ix_drivers_id'), table_name='drivers')
    op.drop_table('drivers')
    op.drop_column('service_requests', 'longitude')
    op.drop_column('service_requests', 'latitude')
    op.drop_column('service_requests', 'phone_number')
    op.drop_column('service_requests', 'name')
    op.drop_column('service_requests', 'vehicle_type')
    op.drop_column('service_requests', 'service_type')
    op.drop_column('users', 'role')
