"""
Repositorio para operaciones CRUD de atletas.

Implementa el acceso a datos para la entidad AthleteModel,
siguiendo el patron Repository.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from loguru import logger

from app.infrastructure.database.models import AthleteModel


class AthleteRepository:
    """
    Repositorio para gestionar atletas en la base de datos.
    
    Proporciona operaciones CRUD completas y metodos especializados
    para filtrado y carga masiva de datos.
    """

    def __init__(self, db: AsyncSession):
        """
        Inicializa el repositorio con una sesion de base de datos.
        
        Args:
            db: Sesion asincrona de SQLAlchemy
        """
        self.db = db

    async def get_all(
        self,
        status: Optional[str] = None,
        discipline: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AthleteModel]:
        """
        Obtiene una lista de atletas con filtros opcionales.
        
        Args:
            status: Filtrar por status (Por generar, Por revisar, Plan activo)
            discipline: Filtrar por disciplina
            limit: Maximo de resultados
            offset: Desplazamiento para paginacion
            
        Returns:
            Lista de AthleteModel
        """
        query = select(AthleteModel)
        
        if status:
            query = query.where(AthleteModel.status == status)
        if discipline:
            query = query.where(AthleteModel.discipline == discipline)
        
        query = query.order_by(AthleteModel.name).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, athlete_id: str) -> Optional[AthleteModel]:
        """
        Obtiene un atleta por su ID.
        
        Args:
            athlete_id: ID unico del atleta
            
        Returns:
            AthleteModel o None si no existe
        """
        query = select(AthleteModel).where(AthleteModel.id == athlete_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, athlete_data: Dict[str, Any]) -> AthleteModel:
        """
        Crea un nuevo atleta en la base de datos.
        
        Args:
            athlete_data: Diccionario con los datos del atleta
            
        Returns:
            AthleteModel creado
        """
        athlete = AthleteModel(
            id=athlete_data["id"],
            name=athlete_data["name"],
            age=athlete_data.get("age"),
            discipline=athlete_data.get("discipline"),
            level=athlete_data.get("level"),
            goal=athlete_data.get("goal"),
            status=athlete_data.get("status", "Por generar"),
            experience=athlete_data.get("experience"),
            personal=athlete_data.get("personal"),
            medica=athlete_data.get("medica"),
            deportiva=athlete_data.get("deportiva"),
            performance=athlete_data.get("performance")
        )
        
        self.db.add(athlete)
        await self.db.flush()
        await self.db.refresh(athlete)
        
        logger.info(f"Atleta creado: {athlete.name} (ID: {athlete.id})")
        return athlete

    async def update(self, athlete_id: str, update_data: Dict[str, Any]) -> Optional[AthleteModel]:
        """
        Actualiza los datos de un atleta existente.
        
        Args:
            athlete_id: ID del atleta a actualizar
            update_data: Diccionario con los campos a actualizar
            
        Returns:
            AthleteModel actualizado o None si no existe
        """
        # Filtrar campos nulos
        filtered_data = {k: v for k, v in update_data.items() if v is not None}
        
        if not filtered_data:
            # No hay nada que actualizar
            return await self.get_by_id(athlete_id)
        
        filtered_data["updated_at"] = datetime.utcnow()
        
        query = (
            update(AthleteModel)
            .where(AthleteModel.id == athlete_id)
            .values(**filtered_data)
        )
        
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.debug(f"Atleta {athlete_id} actualizado")
            return await self.get_by_id(athlete_id)
        
        return None

    async def update_status(self, athlete_id: str, new_status: str) -> bool:
        """
        Actualiza solo el status de un atleta.
        
        Args:
            athlete_id: ID del atleta
            new_status: Nuevo status (Por generar, Por revisar, Plan activo)
            
        Returns:
            True si se actualizo, False si no existe
        """
        query = (
            update(AthleteModel)
            .where(AthleteModel.id == athlete_id)
            .values(
                status=new_status,
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.debug(f"Status del atleta {athlete_id} actualizado a '{new_status}'")
            return True
        
        return False

    async def delete(self, athlete_id: str) -> bool:
        """
        Elimina un atleta de la base de datos.
        
        Args:
            athlete_id: ID del atleta a eliminar
            
        Returns:
            True si se elimino, False si no existia
        """
        query = delete(AthleteModel).where(AthleteModel.id == athlete_id)
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.info(f"Atleta {athlete_id} eliminado")
            return True
        
        return False

    async def count(self, status: Optional[str] = None) -> int:
        """
        Cuenta el numero de atletas, opcionalmente filtrados por status.
        
        Args:
            status: Filtrar por status (opcional)
            
        Returns:
            Numero de atletas
        """
        from sqlalchemy import func
        
        query = select(func.count(AthleteModel.id))
        
        if status:
            query = query.where(AthleteModel.status == status)
        
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_status_counts(self) -> Dict[str, int]:
        """
        Obtiene el conteo de atletas por cada status.
        
        Returns:
            Diccionario con conteos por status
        """
        from sqlalchemy import func
        
        query = (
            select(AthleteModel.status, func.count(AthleteModel.id))
            .group_by(AthleteModel.status)
        )
        
        result = await self.db.execute(query)
        rows = result.all()
        
        # Inicializar con ceros
        counts = {
            "Por generar": 0,
            "Por revisar": 0,
            "Plan activo": 0
        }
        
        for status, count in rows:
            if status in counts:
                counts[status] = count
        
        return counts

    async def seed_from_data(self, athletes_data: List[Dict[str, Any]]) -> int:
        """
        Carga masiva de atletas desde una lista de datos.
        Usa upsert (insert or update) para manejar duplicados.
        
        Args:
            athletes_data: Lista de diccionarios con datos de atletas
            
        Returns:
            Numero de atletas procesados
        """
        count = 0
        
        for athlete_data in athletes_data:
            athlete_id = athlete_data.get("id")
            if not athlete_id:
                continue
            
            # Verificar si existe
            existing = await self.get_by_id(athlete_id)
            
            if existing:
                # Actualizar solo si tiene datos nuevos significativos
                await self.update(athlete_id, athlete_data)
            else:
                # Crear nuevo
                await self.create(athlete_data)
            
            count += 1
        
        logger.info(f"Seed completado: {count} atletas procesados")
        return count

    async def exists(self, athlete_id: str) -> bool:
        """
        Verifica si un atleta existe.
        
        Args:
            athlete_id: ID del atleta
            
        Returns:
            True si existe, False en caso contrario
        """
        query = select(AthleteModel.id).where(AthleteModel.id == athlete_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
