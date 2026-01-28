"""add_tp_username

Agrega columna tp_username para almacenar el username de TrainingPeaks del atleta.

Revision ID: c4a34c5db694
Revises: 7143a39f5064
Create Date: 2026-01-19 22:41:07.083890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4a34c5db694'
down_revision: Union[str, Sequence[str], None] = '7143a39f5064'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega columna tp_username a la tabla athletes."""
    op.add_column('athletes', sa.Column('tp_username', sa.String(), nullable=True))


def downgrade() -> None:
    """Elimina columna tp_username de la tabla athletes."""
    op.drop_column('athletes', 'tp_username')
