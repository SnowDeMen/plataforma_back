"""fix_training_status_default

Revision ID: 045b3c322f88
Revises: 225a9b5a26e4
Create Date: 2026-02-28 00:23:50.608206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '045b3c322f88'
down_revision: Union[str, Sequence[str], None] = '225a9b5a26e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update existing NULL values
    op.execute("UPDATE athletes SET training_status = 'Por generar' WHERE training_status IS NULL")
    
    # Set the default value for the column
    op.alter_column('athletes', 'training_status',
                    existing_type=sa.String(length=50),
                    server_default='Por generar',
                    existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('athletes', 'training_status',
                    existing_type=sa.String(length=50),
                    server_default=None,
                    existing_nullable=True)
