"""add_system_settings

Revision ID: 5ca963d90811
Revises: 003_add_last_training
Create Date: 2026-02-03 18:56:18.679802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, Sequence[str], None] = '003_add_last_training'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if not inspector.has_table('system_settings'):
        op.create_table('system_settings',
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('key')
        )
        op.create_index(op.f('ix_system_settings_key'), 'system_settings', ['key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if inspector.has_table('system_settings'):
        indexes = [idx['name'] for idx in inspector.get_indexes('system_settings')]
        if 'ix_system_settings_key' in indexes:
            op.drop_index(op.f('ix_system_settings_key'), table_name='system_settings')
        op.drop_table('system_settings')
