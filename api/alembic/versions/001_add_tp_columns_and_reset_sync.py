"""Agregar columnas TrainingPeaks y resetear cursor de sync

Revision ID: 001_tp_sync
Revises: 
Create Date: 2026-01-27

Cambios:
- Agregar columna tp_username a athletes (Cuenta TrainingPeaks)
- Agregar columna tp_name a athletes (Nombre validado en TP)
- Resetear cursor de sync_state para forzar full sync con nuevo mapeo
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001_tp_sync'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agregar columnas de TrainingPeaks a athletes
    op.add_column('athletes', sa.Column('tp_username', sa.String(), nullable=True))
    op.add_column('athletes', sa.Column('tp_name', sa.String(), nullable=True))
    
    # Resetear cursor de sync_state para forzar full sync
    # Esto permite que el nuevo mapeo de "Nombre Completo" y "Cuenta TrainingPeaks"
    # se aplique a todos los registros existentes
    op.execute("""
        UPDATE sync_state 
        SET cursor_last_modified = '1970-01-01T00:00:00Z'
        WHERE source_table = 'Formulario_Inicial'
    """)


def downgrade() -> None:
    # Eliminar columnas de TrainingPeaks
    op.drop_column('athletes', 'tp_name')
    op.drop_column('athletes', 'tp_username')
    
    # Nota: No se restaura el cursor porque no tiene sentido
    # volver a un estado anterior del sync
