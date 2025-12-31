"""
Repositorio para operaciones de persistencia de TrainingPlan.
Maneja el almacenamiento y recuperacion de planes de entrenamiento.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from app.infrastructure.database.models import TrainingPlanModel


class PlanRepository:
    """
    Repositorio para operaciones CRUD de TrainingPlan.
    
    Proporciona metodos para:
    - Crear planes de entrenamiento
    - Actualizar estado y progreso
    - Recuperar planes por atleta o estado
    """
    
    def __init__(self, db: AsyncSession):
        """
        Inicializa el repositorio con una sesion de base de datos.
        
        Args:
            db: Sesion asincrona de SQLAlchemy
        """
        self.db = db
    
    async def create(
        self,
        athlete_id: str,
        athlete_name: str,
        athlete_context: Optional[Dict[str, Any]] = None,
        weeks: int = 4,
        start_date: Optional[date] = None
    ) -> TrainingPlanModel:
        """
        Crea un nuevo plan de entrenamiento.
        
        Args:
            athlete_id: ID del atleta
            athlete_name: Nombre del atleta
            athlete_context: Contexto del atleta para generacion
            weeks: Numero de semanas del plan
            start_date: Fecha de inicio del plan
            
        Returns:
            TrainingPlanModel: Modelo creado
        """
        # Calcular fecha de fin si hay fecha de inicio
        end_date = None
        if start_date:
            from datetime import timedelta
            end_date = start_date + timedelta(weeks=weeks)
        
        plan = TrainingPlanModel(
            athlete_id=athlete_id,
            athlete_name=athlete_name,
            athlete_context=athlete_context,
            status="pending",
            weeks=weeks,
            start_date=start_date,
            end_date=end_date,
            generation_progress=0,
            generation_message="Plan creado, pendiente de generar"
        )
        
        self.db.add(plan)
        await self.db.flush()
        await self.db.refresh(plan)
        
        logger.info(f"TrainingPlan creado: {plan.id} para atleta {athlete_name}")
        
        return plan
    
    async def get_by_id(self, plan_id: int) -> Optional[TrainingPlanModel]:
        """
        Obtiene un plan por su ID.
        
        Args:
            plan_id: ID del plan
            
        Returns:
            TrainingPlanModel o None si no existe
        """
        query = select(TrainingPlanModel).where(TrainingPlanModel.id == plan_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_athlete(
        self, 
        athlete_id: str,
        status: Optional[str] = None
    ) -> List[TrainingPlanModel]:
        """
        Obtiene todos los planes de un atleta.
        
        Args:
            athlete_id: ID del atleta
            status: Filtrar por estado (opcional)
            
        Returns:
            Lista de TrainingPlanModel
        """
        query = select(TrainingPlanModel).where(
            TrainingPlanModel.athlete_id == athlete_id
        )
        
        if status:
            query = query.where(TrainingPlanModel.status == status)
        
        query = query.order_by(TrainingPlanModel.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_status(self, status: str) -> List[TrainingPlanModel]:
        """
        Obtiene todos los planes con un estado especifico.
        
        Args:
            status: Estado a buscar
            
        Returns:
            Lista de TrainingPlanModel
        """
        query = select(TrainingPlanModel).where(
            TrainingPlanModel.status == status
        ).order_by(TrainingPlanModel.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_latest_by_athlete(self, athlete_id: str) -> Optional[TrainingPlanModel]:
        """
        Obtiene el plan mas reciente de un atleta.
        
        Args:
            athlete_id: ID del atleta
            
        Returns:
            TrainingPlanModel o None
        """
        query = select(TrainingPlanModel).where(
            TrainingPlanModel.athlete_id == athlete_id
        ).order_by(TrainingPlanModel.created_at.desc()).limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def update_status(
        self, 
        plan_id: int, 
        status: str,
        approved_at: Optional[datetime] = None,
        applied_at: Optional[datetime] = None
    ) -> bool:
        """
        Actualiza el estado de un plan.
        
        Args:
            plan_id: ID del plan
            status: Nuevo estado
            approved_at: Timestamp de aprobacion (opcional)
            applied_at: Timestamp de aplicacion (opcional)
            
        Returns:
            True si se actualizo correctamente
        """
        values = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if approved_at:
            values["approved_at"] = approved_at
        if applied_at:
            values["applied_at"] = applied_at
        
        query = (
            update(TrainingPlanModel)
            .where(TrainingPlanModel.id == plan_id)
            .values(**values)
        )
        
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.info(f"Plan {plan_id} actualizado a estado: {status}")
            return True
        
        return False
    
    async def update_progress(
        self, 
        plan_id: int, 
        progress: int,
        message: str
    ) -> bool:
        """
        Actualiza el progreso de generacion de un plan.
        
        Args:
            plan_id: ID del plan
            progress: Porcentaje de progreso (0-100)
            message: Mensaje de estado
            
        Returns:
            True si se actualizo correctamente
        """
        query = (
            update(TrainingPlanModel)
            .where(TrainingPlanModel.id == plan_id)
            .values(
                generation_progress=progress,
                generation_message=message,
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db.execute(query)
        return result.rowcount > 0
    
    async def update_plan_data(
        self, 
        plan_id: int,
        plan_data: Dict[str, Any],
        plan_summary: Optional[str] = None
    ) -> bool:
        """
        Actualiza los datos del plan generado.
        
        Args:
            plan_id: ID del plan
            plan_data: Datos del plan (workouts estructurados)
            plan_summary: Resumen del plan
            
        Returns:
            True si se actualizo correctamente
        """
        values = {
            "plan_data": plan_data,
            "updated_at": datetime.utcnow()
        }
        
        if plan_summary:
            values["plan_summary"] = plan_summary
        
        query = (
            update(TrainingPlanModel)
            .where(TrainingPlanModel.id == plan_id)
            .values(**values)
        )
        
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.debug(f"Plan data actualizado para plan {plan_id}")
            return True
        
        return False
    
    async def update_generation_prompt(
        self, 
        plan_id: int,
        prompt: str
    ) -> bool:
        """
        Guarda el prompt usado para generar el plan.
        
        Args:
            plan_id: ID del plan
            prompt: Prompt de generacion
            
        Returns:
            True si se actualizo correctamente
        """
        query = (
            update(TrainingPlanModel)
            .where(TrainingPlanModel.id == plan_id)
            .values(
                generation_prompt=prompt,
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db.execute(query)
        return result.rowcount > 0
    
    async def delete(self, plan_id: int) -> bool:
        """
        Elimina un plan de entrenamiento.
        
        Args:
            plan_id: ID del plan a eliminar
            
        Returns:
            True si se elimino correctamente
        """
        plan = await self.get_by_id(plan_id)
        
        if not plan:
            logger.warning(f"Plan no encontrado para eliminar: {plan_id}")
            return False
        
        await self.db.delete(plan)
        logger.info(f"TrainingPlan eliminado: {plan_id}")
        return True
    
    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[TrainingPlanModel]:
        """
        Obtiene todos los planes con paginacion.
        
        Args:
            limit: Cantidad maxima de resultados
            offset: Desplazamiento para paginacion
            status: Filtrar por estado (opcional)
            
        Returns:
            Lista de TrainingPlanModel
        """
        query = select(TrainingPlanModel)
        
        if status:
            query = query.where(TrainingPlanModel.status == status)
        
        query = query.order_by(
            TrainingPlanModel.created_at.desc()
        ).limit(limit).offset(offset)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())

