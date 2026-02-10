"""separate_client_and_training_statuses

Revision ID: 96e526350227
Revises: dad74ed39676
Create Date: 2026-02-09 21:43:51.940862

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, Sequence[str], None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename status to training_status
    op.alter_column('athletes', 'status', new_column_name='training_status')
    
    # Unificar 'Por Revisar' a 'Por revisar' y asegurar valores por defecto
    op.execute("""
        UPDATE athletes 
        SET training_status = 'Por revisar' 
        WHERE training_status = 'Por Revisar'
    """)
    op.execute("""
        UPDATE athletes 
        SET training_status = 'Por generar' 
        WHERE training_status IS NULL
    """)


def downgrade() -> None:
    # Rename training_status back to status
    op.alter_column('athletes', 'training_status', new_column_name='status')
