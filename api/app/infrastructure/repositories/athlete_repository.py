"""
Implementación del repositorio de atletas.
Maneja las operaciones de base de datos para la entidad AthleteModel.
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import AthleteModel


class AthleteRepository:
    """Repositorio para gestionar atletas en la base de datos."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self) -> List[AthleteModel]:
        """
        Obtiene todos los atletas activos (no eliminados).
        """
        result = await self.db.execute(
            select(AthleteModel).where(AthleteModel.is_deleted == False)
        )
        return result.scalars().all()
    
    async def get_by_id(self, athlete_id: str) -> Optional[AthleteModel]:
        """
        Obtiene un atleta por su ID de Airtable.
        """
        result = await self.db.execute(
            select(AthleteModel).where(AthleteModel.airtable_record_id == athlete_id)
        )
        return result.scalars().first()
