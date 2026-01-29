"""Convertir training_start_date de String a Date

Revision ID: 002_training_date
Revises: 001_tp_sync
Create Date: 2026-01-27

Cambios:
- Convertir columna training_start_date de VARCHAR a DATE
- Migrar datos existentes parseando el formato ISO 8601
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_training_date'
down_revision: Union[str, None] = '001_tp_sync'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convierte training_start_date de VARCHAR a DATE."""
    # PostgreSQL: ALTER COLUMN con USING para convertir datos existentes
    # El cast ::DATE parsea automaticamente el formato ISO 8601 (YYYY-MM-DD)
    op.execute("""
        ALTER TABLE athletes 
        ALTER COLUMN training_start_date 
        TYPE DATE 
        USING training_start_date::DATE
    """)


def downgrade() -> None:
    """Revierte training_start_date a VARCHAR."""
    op.execute("""
        ALTER TABLE athletes 
        ALTER COLUMN training_start_date 
        TYPE VARCHAR 
        USING training_start_date::VARCHAR
    """)
