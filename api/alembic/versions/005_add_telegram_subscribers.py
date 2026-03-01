"""add_telegram_subscribers

Revision ID: dad74ed39676
Revises: 5ca963d90811
Create Date: 2026-02-03 19:33:00.277127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, Sequence[str], None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if not inspector.has_table('telegram_subscribers'):
        op.create_table('telegram_subscribers',
            sa.Column('chat_id', sa.String(length=255), nullable=False),
            sa.Column('username', sa.String(length=255), nullable=True),
            sa.Column('first_name', sa.String(length=255), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('chat_id')
        )
        op.create_index(op.f('ix_telegram_subscribers_chat_id'), 'telegram_subscribers', ['chat_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if inspector.has_table('telegram_subscribers'):
        indexes = [idx['name'] for idx in inspector.get_indexes('telegram_subscribers')]
        if 'ix_telegram_subscribers_chat_id' in indexes:
            op.drop_index(op.f('ix_telegram_subscribers_chat_id'), table_name='telegram_subscribers')
        op.drop_table('telegram_subscribers')
