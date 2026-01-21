"""add_tp_name

Agrega columna tp_name para almacenar el nombre del atleta en TrainingPeaks.

Revision ID: 2b7f2c054832
Revises: c4a34c5db694
Create Date: 2026-01-20 22:26:53.419263

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2b7f2c054832'
down_revision: Union[str, Sequence[str], None] = 'c4a34c5db694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega columna tp_name a la tabla athletes."""
    op.add_column('athletes', sa.Column('tp_name', sa.String(), nullable=True))


def downgrade() -> None:
    """Elimina columna tp_name de la tabla athletes."""
    op.drop_column('athletes', 'tp_name')
