"""003_add_last_training

Revision ID: 003_add_last_training
Revises: 002_training_date
Create Date: 2026-01-29 23:35:05.326105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_last_training'
down_revision: Union[str, None] = '002_training_date'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Check if column exists before adding
    columns = [col['name'] for col in inspector.get_columns('athletes')]
    if 'last_training_generation_at' not in columns:
        op.add_column('athletes', sa.Column('last_training_generation_at', sa.DateTime(timezone=True), nullable=True))
    
    # Check if index exists before creating
    indexes = [idx['name'] for idx in inspector.get_indexes('chat_sessions')]
    if 'ix_chat_sessions_athlete_id' not in indexes:
        op.create_index(op.f('ix_chat_sessions_athlete_id'), 'chat_sessions', ['athlete_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    indexes = [idx['name'] for idx in inspector.get_indexes('chat_sessions')]
    if 'ix_chat_sessions_athlete_id' in indexes:
        op.drop_index(op.f('ix_chat_sessions_athlete_id'), table_name='chat_sessions')
        
    columns = [col['name'] for col in inspector.get_columns('athletes')]
    if 'last_training_generation_at' in columns:
        op.drop_column('athletes', 'last_training_generation_at')
