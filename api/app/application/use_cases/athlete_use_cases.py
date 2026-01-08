"""
Casos de uso para la gestion de atletas.

Implementa la logica de negocio para operaciones con atletas,
siguiendo el patron de arquitectura limpia.
"""
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.application.dto.athlete_dto import (
    AthleteDTO,
    AthleteListItemDTO,
    AthleteUpdateDTO,
    AthleteStatusUpdateDTO,
    AthleteCreateDTO
)
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.shared.exceptions.domain import EntityNotFoundException


class AthleteNotFoundException(EntityNotFoundException):
    """Excepcion cuando no se encuentra un atleta."""
    
    def __init__(self, athlete_id: str):
        super().__init__(
            message=f"Atleta con ID '{athlete_id}' no encontrado",
            error_code="ATHLETE_NOT_FOUND",
            details={"athlete_id": athlete_id}
        )
        self.status_code = 404


class AthleteUseCases:
    """
    Casos de uso para operaciones con atletas.
    
    Encapsula la logica de negocio relacionada con la gestion
    de atletas, incluyendo listado, consulta, actualizacion y seed.
    """

    def __init__(self, db: AsyncSession):
        """
        Inicializa los casos de uso con una sesion de base de datos.
        
        Args:
            db: Sesion asincrona de SQLAlchemy
        """
        self.db = db
        self.repository = AthleteRepository(db)

    async def list_athletes(
        self,
        status: Optional[str] = None,
        discipline: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AthleteListItemDTO]:
        """
        Lista atletas con filtros opcionales.
        
        Args:
            status: Filtrar por status
            discipline: Filtrar por disciplina
            limit: Maximo de resultados
            offset: Desplazamiento para paginacion
            
        Returns:
            Lista de AthleteListItemDTO
        """
        athletes = await self.repository.get_all(
            status=status,
            discipline=discipline,
            limit=limit,
            offset=offset
        )
        
        return [
            AthleteListItemDTO(
                id=a.id,
                name=a.name,
                age=a.age,
                discipline=a.discipline,
                level=a.level,
                status=a.status,
                goal=a.goal
            )
            for a in athletes
        ]

    async def get_athlete(self, athlete_id: str) -> AthleteDTO:
        """
        Obtiene el detalle completo de un atleta.
        
        Args:
            athlete_id: ID del atleta
            
        Returns:
            AthleteDTO con todos los datos
            
        Raises:
            AthleteNotFoundException: Si el atleta no existe
        """
        athlete = await self.repository.get_by_id(athlete_id)
        
        if not athlete:
            raise AthleteNotFoundException(athlete_id)
        
        return AthleteDTO(
            id=athlete.id,
            name=athlete.name,
            age=athlete.age,
            discipline=athlete.discipline,
            level=athlete.level,
            goal=athlete.goal,
            status=athlete.status,
            experience=athlete.experience,
            personal=athlete.personal,
            medica=athlete.medica,
            deportiva=athlete.deportiva,
            performance=athlete.performance
        )

    async def update_athlete(self, athlete_id: str, dto: AthleteUpdateDTO) -> AthleteDTO:
        """
        Actualiza los datos de un atleta.
        
        Args:
            athlete_id: ID del atleta a actualizar
            dto: Datos a actualizar
            
        Returns:
            AthleteDTO actualizado
            
        Raises:
            AthleteNotFoundException: Si el atleta no existe
        """
        # Verificar existencia
        if not await self.repository.exists(athlete_id):
            raise AthleteNotFoundException(athlete_id)
        
        # Convertir DTO a diccionario excluyendo None
        update_data = dto.model_dump(exclude_none=True)
        
        # Actualizar
        updated = await self.repository.update(athlete_id, update_data)
        await self.db.commit()
        
        logger.info(f"Atleta {athlete_id} actualizado")
        
        return AthleteDTO(
            id=updated.id,
            name=updated.name,
            age=updated.age,
            discipline=updated.discipline,
            level=updated.level,
            goal=updated.goal,
            status=updated.status,
            experience=updated.experience,
            personal=updated.personal,
            medica=updated.medica,
            deportiva=updated.deportiva,
            performance=updated.performance
        )

    async def update_status(self, athlete_id: str, dto: AthleteStatusUpdateDTO) -> AthleteDTO:
        """
        Actualiza solo el status de un atleta.
        
        Args:
            athlete_id: ID del atleta
            dto: DTO con el nuevo status
            
        Returns:
            AthleteDTO actualizado
            
        Raises:
            AthleteNotFoundException: Si el atleta no existe
        """
        success = await self.repository.update_status(athlete_id, dto.status)
        
        if not success:
            raise AthleteNotFoundException(athlete_id)
        
        await self.db.commit()
        
        logger.info(f"Status del atleta {athlete_id} cambiado a '{dto.status}'")
        
        return await self.get_athlete(athlete_id)

    async def create_athlete(self, dto: AthleteCreateDTO) -> AthleteDTO:
        """
        Crea un nuevo atleta.
        
        Args:
            dto: Datos del atleta a crear
            
        Returns:
            AthleteDTO creado
        """
        athlete_data = dto.model_dump()
        athlete = await self.repository.create(athlete_data)
        await self.db.commit()
        
        return AthleteDTO(
            id=athlete.id,
            name=athlete.name,
            age=athlete.age,
            discipline=athlete.discipline,
            level=athlete.level,
            goal=athlete.goal,
            status=athlete.status,
            experience=athlete.experience,
            personal=athlete.personal,
            medica=athlete.medica,
            deportiva=athlete.deportiva,
            performance=athlete.performance
        )

    async def seed_athletes(self, athletes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Carga masiva de atletas desde datos externos.
        
        Args:
            athletes_data: Lista de diccionarios con datos de atletas
            
        Returns:
            Diccionario con estadisticas del seed
        """
        count = await self.repository.seed_from_data(athletes_data)
        await self.db.commit()
        
        logger.info(f"Seed de atletas completado: {count} registros procesados")
        
        return {
            "processed": count,
            "message": f"Se procesaron {count} atletas correctamente"
        }

    async def get_status_counts(self) -> Dict[str, int]:
        """
        Obtiene el conteo de atletas por status.
        
        Returns:
            Diccionario con conteos por status
        """
        return await self.repository.get_status_counts()

    async def delete_athlete(self, athlete_id: str) -> bool:
        """
        Elimina un atleta.
        
        Args:
            athlete_id: ID del atleta a eliminar
            
        Returns:
            True si se elimino
            
        Raises:
            AthleteNotFoundException: Si el atleta no existe
        """
        success = await self.repository.delete(athlete_id)
        
        if not success:
            raise AthleteNotFoundException(athlete_id)
        
        await self.db.commit()
        
        logger.info(f"Atleta {athlete_id} eliminado")
        return True

