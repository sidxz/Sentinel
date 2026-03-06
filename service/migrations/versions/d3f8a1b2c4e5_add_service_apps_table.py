"""add_service_apps_table

Revision ID: d3f8a1b2c4e5
Revises: 9ea1bf38293e
Create Date: 2026-03-05 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd3f8a1b2c4e5'
down_revision: Union[str, None] = '9ea1bf38293e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'service_apps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('service_name', sa.String(length=255), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=12), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name'),
    )
    op.create_index('ix_service_apps_key_hash', 'service_apps', ['key_hash'], unique=True)
    op.create_index('ix_service_apps_is_active', 'service_apps', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_service_apps_is_active', table_name='service_apps')
    op.drop_index('ix_service_apps_key_hash', table_name='service_apps')
    op.drop_table('service_apps')
