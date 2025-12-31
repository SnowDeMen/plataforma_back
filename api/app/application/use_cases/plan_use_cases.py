"""
Casos de uso para operaciones de planes de entrenamiento.
Contiene la logica de negocio para generar, aprobar y gestionar planes.
"""
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, date
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.application.dto.plan_dto import (
    PlanGenerationRequestDTO,
    TrainingPlanDTO,
    PlanProgressDTO,
    PlanListItemDTO,
    PlanWorkoutDTO,
    WeekSummaryDTO,
    PlanApprovalDTO,
    PlanModifyRequestDTO,
    PlanModifyResponseDTO,
    PlanModifyChangeDTO,
    SafeAlternativeDTO,
    SafeAlternativeWorkoutDTO,
    PlanModificationHistoryDTO,
    ModificationHistoryEntryDTO
)
from app.infrastructure.repositories.plan_repository import PlanRepository
from app.infrastructure.autogen.plan_generator import PlanGenerator
from app.shared.exceptions.domain import PlanNotFoundException


class PlanUseCases:
    """
    Casos de uso para operaciones de planes de entrenamiento.
    
    Maneja la generacion asincrona de planes, aprobacion/rechazo
    y consulta de planes existentes.
    """
    
    # Almacenamiento temporal de callbacks de progreso por plan_id
    _progress_callbacks: Dict[int, List[Callable[[int, str], None]]] = {}
    
    def __init__(self, db: AsyncSession):
        """
        Inicializa los casos de uso con una sesion de base de datos.
        
        Args:
            db: Sesion asincrona de SQLAlchemy
        """
        self.db = db
        self.repository = PlanRepository(db)
        self.generator = PlanGenerator()
    
    @classmethod
    def register_progress_callback(
        cls, 
        plan_id: int, 
        callback: Callable[[int, str], None]
    ) -> None:
        """
        Registra un callback para recibir actualizaciones de progreso.
        
        Args:
            plan_id: ID del plan
            callback: Funcion que recibe (progress%, message)
        """
        if plan_id not in cls._progress_callbacks:
            cls._progress_callbacks[plan_id] = []
        cls._progress_callbacks[plan_id].append(callback)
    
    @classmethod
    def unregister_progress_callback(
        cls, 
        plan_id: int, 
        callback: Callable[[int, str], None]
    ) -> None:
        """
        Elimina un callback de progreso.
        
        Args:
            plan_id: ID del plan
            callback: Callback a eliminar
        """
        if plan_id in cls._progress_callbacks:
            try:
                cls._progress_callbacks[plan_id].remove(callback)
            except ValueError:
                pass
    
    @classmethod
    def _notify_progress(cls, plan_id: int, progress: int, message: str) -> None:
        """
        Notifica a todos los callbacks registrados del progreso.
        
        Args:
            plan_id: ID del plan
            progress: Porcentaje de progreso
            message: Mensaje de estado
        """
        callbacks = cls._progress_callbacks.get(plan_id, [])
        for callback in callbacks:
            try:
                callback(progress, message)
            except Exception as e:
                logger.warning(f"Error en callback de progreso: {e}")
    
    async def create_plan(
        self,
        dto: PlanGenerationRequestDTO
    ) -> TrainingPlanDTO:
        """
        Crea un nuevo plan de entrenamiento (sin generar aun).
        
        Args:
            dto: Datos de la solicitud de generacion
            
        Returns:
            TrainingPlanDTO con el plan creado en estado pending
        """
        # Construir contexto del atleta
        athlete_context = {
            'athlete_id': dto.athlete_id,
            'athlete_name': dto.athlete_name,
            'age': dto.athlete_info.age,
            'discipline': dto.athlete_info.discipline,
            'level': dto.athlete_info.level,
            'goal': dto.athlete_info.goal,
            'experience': dto.athlete_info.experience,
            'personal': dto.athlete_info.personal,
            'medica': dto.athlete_info.medica,
            'deportiva': dto.athlete_info.deportiva,
            'performance': dto.athlete_info.performance
        }
        
        # Crear plan en BD
        plan = await self.repository.create(
            athlete_id=dto.athlete_id,
            athlete_name=dto.athlete_name,
            athlete_context=athlete_context,
            weeks=dto.weeks,
            start_date=dto.start_date
        )
        
        await self.db.commit()
        
        logger.info(f"Plan creado: {plan.id} para atleta {dto.athlete_name}")
        
        return self._to_dto(plan)
    
    async def generate_plan(
        self,
        plan_id: int,
        on_progress: Optional[Callable[[int, str], None]] = None
    ) -> TrainingPlanDTO:
        """
        Genera el contenido de un plan existente.
        
        Args:
            plan_id: ID del plan a generar
            on_progress: Callback para reportar progreso
            
        Returns:
            TrainingPlanDTO con el plan generado
            
        Raises:
            PlanNotFoundException: Si el plan no existe
        """
        # Obtener plan
        plan = await self.repository.get_by_id(plan_id)
        
        if not plan:
            raise PlanNotFoundException(plan_id)
        
        # Actualizar estado a generating
        await self.repository.update_status(plan_id, "generating")
        await self.repository.update_progress(plan_id, 0, "Iniciando generacion...")
        await self.db.commit()
        
        # Funcion para manejar progreso
        async def handle_progress(progress: int, message: str):
            await self.repository.update_progress(plan_id, progress, message)
            await self.db.commit()
            
            # Notificar callbacks registrados
            self._notify_progress(plan_id, progress, message)
            
            # Llamar callback local si existe
            if on_progress:
                on_progress(progress, message)
        
        try:
            # Generar plan
            plan_data = await self.generator.generate(
                athlete_context=plan.athlete_context or {},
                start_date=plan.start_date,
                on_progress=lambda p, m: asyncio.create_task(handle_progress(p, m))
            )
            
            # Calcular totales
            totals = self.generator.calculate_totals(plan_data)
            
            # Construir resumen
            summary = plan_data.get('summary', '')
            if not summary:
                summary = (
                    f"Plan de {plan.weeks} semanas para {plan.athlete_name}. "
                    f"Total: {totals['training_days']} dias de entrenamiento, "
                    f"{totals['rest_days']} dias de descanso. "
                    f"TSS total: {totals['total_tss']}, "
                    f"Distancia: {totals['total_distance_km']} km."
                )
            
            # Actualizar plan con datos generados
            await self.repository.update_plan_data(plan_id, plan_data, summary)
            await self.repository.update_status(plan_id, "review")
            await self.repository.update_progress(plan_id, 100, "Plan generado exitosamente")
            await self.db.commit()
            
            # Refrescar plan
            plan = await self.repository.get_by_id(plan_id)
            
            logger.info(
                f"Plan {plan_id} generado: {totals['workout_count']} workouts, "
                f"TSS: {totals['total_tss']}"
            )
            
            return self._to_dto(plan)
            
        except Exception as e:
            logger.error(f"Error generando plan {plan_id}: {e}")
            await self.repository.update_status(plan_id, "pending")
            await self.repository.update_progress(plan_id, 0, f"Error: {str(e)}")
            await self.db.commit()
            raise
    
    async def create_and_generate(
        self,
        dto: PlanGenerationRequestDTO,
        on_progress: Optional[Callable[[int, str], None]] = None
    ) -> TrainingPlanDTO:
        """
        Crea y genera un plan en un solo paso.
        
        Combina create_plan y generate_plan.
        
        Args:
            dto: Datos de la solicitud
            on_progress: Callback para progreso
            
        Returns:
            TrainingPlanDTO con el plan generado
        """
        # Crear plan
        plan_dto = await self.create_plan(dto)
        
        # Generar contenido
        return await self.generate_plan(plan_dto.id, on_progress)
    
    async def approve_plan(
        self, 
        plan_id: int,
        dto: Optional[PlanApprovalDTO] = None
    ) -> TrainingPlanDTO:
        """
        Aprueba un plan de entrenamiento.
        
        Cambia el estado a 'active' y marca la fecha de aprobacion.
        
        Args:
            plan_id: ID del plan
            dto: Datos de aprobacion (opcional)
            
        Returns:
            TrainingPlanDTO actualizado
            
        Raises:
            PlanNotFoundException: Si el plan no existe
        """
        plan = await self.repository.get_by_id(plan_id)
        
        if not plan:
            raise PlanNotFoundException(plan_id)
        
        await self.repository.update_status(
            plan_id, 
            "active",
            approved_at=datetime.utcnow()
        )
        await self.db.commit()
        
        plan = await self.repository.get_by_id(plan_id)
        
        logger.info(f"Plan {plan_id} aprobado")
        
        return self._to_dto(plan)
    
    async def reject_plan(
        self, 
        plan_id: int,
        dto: Optional[PlanApprovalDTO] = None
    ) -> TrainingPlanDTO:
        """
        Rechaza un plan de entrenamiento.
        
        Cambia el estado a 'rejected'.
        
        Args:
            plan_id: ID del plan
            dto: Datos de rechazo con feedback (opcional)
            
        Returns:
            TrainingPlanDTO actualizado
            
        Raises:
            PlanNotFoundException: Si el plan no existe
        """
        plan = await self.repository.get_by_id(plan_id)
        
        if not plan:
            raise PlanNotFoundException(plan_id)
        
        await self.repository.update_status(plan_id, "rejected")
        await self.db.commit()
        
        plan = await self.repository.get_by_id(plan_id)
        
        logger.info(f"Plan {plan_id} rechazado")
        
        return self._to_dto(plan)
    
    async def get_plan(self, plan_id: int) -> TrainingPlanDTO:
        """
        Obtiene un plan por ID.
        
        Args:
            plan_id: ID del plan
            
        Returns:
            TrainingPlanDTO
            
        Raises:
            PlanNotFoundException: Si no existe
        """
        plan = await self.repository.get_by_id(plan_id)
        
        if not plan:
            raise PlanNotFoundException(plan_id)
        
        return self._to_dto(plan)
    
    async def get_plan_progress(self, plan_id: int) -> PlanProgressDTO:
        """
        Obtiene el progreso de generacion de un plan.
        
        Args:
            plan_id: ID del plan
            
        Returns:
            PlanProgressDTO con el estado actual
        """
        plan = await self.repository.get_by_id(plan_id)
        
        if not plan:
            raise PlanNotFoundException(plan_id)
        
        # Contar workouts si hay plan_data
        total_workouts = 28  # Default para 4 semanas
        current_workout = 0
        
        if plan.plan_data:
            workouts = self.generator.extract_workouts_flat(plan.plan_data)
            current_workout = len(workouts)
        
        return PlanProgressDTO(
            plan_id=plan.id,
            status=plan.status,
            progress=plan.generation_progress or 0,
            current_week=None,  # Se podria calcular
            current_workout=current_workout,
            total_workouts=total_workouts,
            message=plan.generation_message or ""
        )
    
    async def get_athlete_plans(
        self, 
        athlete_id: str,
        status: Optional[str] = None
    ) -> List[PlanListItemDTO]:
        """
        Obtiene todos los planes de un atleta.
        
        Args:
            athlete_id: ID del atleta
            status: Filtrar por estado (opcional)
            
        Returns:
            Lista de PlanListItemDTO
        """
        plans = await self.repository.get_by_athlete(athlete_id, status)
        
        return [self._to_list_item_dto(plan) for plan in plans]
    
    async def get_plans_by_status(self, status: str) -> List[PlanListItemDTO]:
        """
        Obtiene todos los planes con un estado especifico.
        
        Args:
            status: Estado a buscar
            
        Returns:
            Lista de PlanListItemDTO
        """
        plans = await self.repository.get_by_status(status)
        
        return [self._to_list_item_dto(plan) for plan in plans]
    
    async def delete_plan(self, plan_id: int) -> bool:
        """
        Elimina un plan de entrenamiento.
        
        Args:
            plan_id: ID del plan
            
        Returns:
            True si se elimino correctamente
        """
        deleted = await self.repository.delete(plan_id)
        
        if deleted:
            await self.db.commit()
            logger.info(f"Plan {plan_id} eliminado")
        
        return deleted
    
    async def modify_plan(
        self, 
        plan_id: int, 
        dto: PlanModifyRequestDTO
    ) -> PlanModifyResponseDTO:
        """
        Modifica un plan existente usando IA.
        
        Incluye deteccion de riesgos: si el cambio es potencialmente peligroso,
        retorna una advertencia con alternativa segura y requiere confirmacion.
        
        Args:
            plan_id: ID del plan a modificar
            dto: Datos de la modificacion (scope, target, prompt, force_apply, use_safe_alternative)
            
        Returns:
            PlanModifyResponseDTO con:
            - requires_confirmation=True si necesita confirmacion (no se aplica cambio)
            - requires_confirmation=False si se aplico el cambio
            
        Raises:
            PlanNotFoundException: Si el plan no existe
            ValueError: Si hay error en la modificacion
        """
        # Obtener plan actual
        plan = await self.repository.get_by_id(plan_id)
        
        if not plan:
            raise PlanNotFoundException(plan_id)
        
        if not plan.plan_data:
            raise ValueError("El plan no tiene datos para modificar")
        
        logger.info(
            f"Modificando plan {plan_id} - scope: {dto.scope}, "
            f"force: {dto.force_apply}, safe_alt: {dto.use_safe_alternative}"
        )
        
        try:
            # Llamar al generador para modificar (con deteccion de riesgos)
            result = await self.generator.modify_plan(
                current_plan=plan.plan_data,
                scope=dto.scope,
                target=dto.target,
                user_prompt=dto.prompt,
                force_apply=dto.force_apply,
                use_safe_alternative=dto.use_safe_alternative
            )
            
            # Verificar si requiere confirmacion
            if result.get('requires_confirmation', False):
                # No se aplica el cambio, solo se retorna la advertencia
                safe_alt = result.get('safe_alternative', {})
                workout_preview = safe_alt.get('workout_preview', {})
                
                return PlanModifyResponseDTO(
                    success=True,
                    message="Se requiere confirmacion para este cambio",
                    requires_confirmation=True,
                    risk_warning=result.get('risk_warning', ''),
                    risk_category=result.get('risk_category', ''),
                    user_request_summary=result.get('user_request_summary', dto.prompt),
                    safe_alternative=SafeAlternativeDTO(
                        description=safe_alt.get('description', ''),
                        workout_preview=SafeAlternativeWorkoutDTO(
                            title=workout_preview.get('title', ''),
                            workout_type=workout_preview.get('workout_type', ''),
                            duration=workout_preview.get('duration'),
                            tss=workout_preview.get('tss'),
                            description=workout_preview.get('description')
                        ) if workout_preview else None
                    ) if safe_alt else None,
                    plan=None,
                    changes=[]
                )
            
            # El cambio se aplico (directo, forzado, o alternativa)
            updated_plan_data = result['plan']
            summary = result['summary']
            changes = result['changes']
            
            # Actualizar plan en BD
            await self.repository.update_plan_data(
                plan_id, 
                updated_plan_data, 
                updated_plan_data.get('summary', plan.plan_summary)
            )
            await self.db.commit()
            
            # Refrescar plan
            plan = await self.repository.get_by_id(plan_id)
            
            logger.info(
                f"Plan {plan_id} modificado ({result.get('decision', 'unknown')}): {summary}"
            )
            
            # Construir respuesta
            return PlanModifyResponseDTO(
                success=True,
                message="Plan modificado exitosamente",
                requires_confirmation=False,
                summary=summary,
                changes=[
                    PlanModifyChangeDTO(
                        type=c.get('type', dto.scope),
                        target=c.get('target', ''),
                        original=c.get('original', ''),
                        new=c.get('new', ''),
                        reason=c.get('reason', '')
                    )
                    for c in changes
                ],
                plan=self._to_dto(plan),
                decision=result.get('decision'),
                had_risk_warning=result.get('had_risk_warning', False)
            )
            
        except Exception as e:
            logger.error(f"Error modificando plan {plan_id}: {e}")
            return PlanModifyResponseDTO(
                success=False,
                message=f"Error al modificar el plan: {str(e)}",
                requires_confirmation=False,
                summary=None,
                changes=[],
                plan=None
            )
    
    async def get_modification_history(
        self, 
        plan_id: int
    ) -> PlanModificationHistoryDTO:
        """
        Obtiene el historial de modificaciones de un plan.
        
        Args:
            plan_id: ID del plan
            
        Returns:
            PlanModificationHistoryDTO con todas las modificaciones
            
        Raises:
            PlanNotFoundException: Si el plan no existe
        """
        plan = await self.repository.get_by_id(plan_id)
        
        if not plan:
            raise PlanNotFoundException(plan_id)
        
        # Extraer historial del plan_data
        modification_history = []
        forced_count = 0
        
        if plan.plan_data:
            raw_history = plan.plan_data.get('modification_history', [])
            
            for entry in raw_history:
                # Convertir cambios a DTOs
                changes = [
                    PlanModifyChangeDTO(
                        type=c.get('type', 'unknown'),
                        target=c.get('target', ''),
                        original=c.get('original', ''),
                        new=c.get('new', ''),
                        reason=c.get('reason', '')
                    )
                    for c in entry.get('changes', [])
                ]
                
                history_entry = ModificationHistoryEntryDTO(
                    id=entry.get('id', len(modification_history) + 1),
                    timestamp=entry.get('timestamp', ''),
                    scope=entry.get('scope', 'unknown'),
                    target=entry.get('target'),
                    user_prompt=entry.get('user_prompt', entry.get('prompt', '')),
                    summary=entry.get('summary', ''),
                    changes=changes,
                    decision=entry.get('decision', 'direct'),
                    had_risk_warning=entry.get('had_risk_warning', False),
                    risk_warning=entry.get('risk_warning'),
                    forced_by_user=entry.get('forced_by_user', False),
                    used_safe_alternative=entry.get('used_safe_alternative', False)
                )
                
                modification_history.append(history_entry)
                
                if entry.get('forced_by_user', False):
                    forced_count += 1
        
        return PlanModificationHistoryDTO(
            plan_id=plan_id,
            athlete_name=plan.athlete_name,
            modifications=modification_history,
            total_modifications=len(modification_history),
            forced_changes_count=forced_count
        )
    
    def _to_dto(self, plan) -> TrainingPlanDTO:
        """Convierte un modelo a DTO completo."""
        workouts = []
        weeks = []
        
        if plan.plan_data:
            # Extraer workouts
            workouts_data = self.generator.extract_workouts_flat(plan.plan_data)
            workouts = [
                PlanWorkoutDTO(
                    day=w.get('day', 0),
                    week=w.get('week', 0),
                    date=w.get('date'),
                    workout_type=w.get('workout_type', 'Run'),
                    title=w.get('title', ''),
                    description=w.get('description'),
                    pre_activity_comments=w.get('pre_activity_comments'),
                    duration=w.get('duration'),
                    distance=w.get('distance'),
                    tss=w.get('tss'),
                    intensity_factor=w.get('intensity_factor'),
                    average_pace=w.get('average_pace'),
                    elevation_gain=w.get('elevation_gain'),
                    calories=w.get('calories')
                )
                for w in workouts_data
            ]
            
            # Extraer semanas
            for week_data in plan.plan_data.get('weeks', []):
                week_workouts = [
                    PlanWorkoutDTO(
                        day=w.get('day', 0),
                        week=week_data.get('week', 0),
                        date=w.get('date'),
                        workout_type=w.get('workout_type', 'Run'),
                        title=w.get('title', ''),
                        description=w.get('description'),
                        pre_activity_comments=w.get('pre_activity_comments'),
                        duration=w.get('duration'),
                        distance=w.get('distance'),
                        tss=w.get('tss'),
                        intensity_factor=w.get('intensity_factor'),
                        average_pace=w.get('average_pace'),
                        elevation_gain=w.get('elevation_gain'),
                        calories=w.get('calories')
                    )
                    for w in week_data.get('workouts', [])
                ]
                
                weeks.append(WeekSummaryDTO(
                    week=week_data.get('week', 0),
                    total_duration=str(week_data.get('total_duration', '0:00:00')),
                    total_distance=str(week_data.get('total_distance_km', 0)),
                    total_tss=week_data.get('total_tss', 0),
                    workout_count=len(week_workouts),
                    rest_days=sum(1 for w in week_workouts if w.workout_type.lower() == 'day off'),
                    focus=week_data.get('focus'),
                    workouts=week_workouts
                ))
        
        # Calcular totales
        totals = {}
        if plan.plan_data:
            totals = self.generator.calculate_totals(plan.plan_data)
        
        return TrainingPlanDTO(
            id=plan.id,
            athlete_id=plan.athlete_id,
            athlete_name=plan.athlete_name,
            status=plan.status,
            weeks_count=plan.weeks,
            start_date=plan.start_date,
            end_date=plan.end_date,
            summary=plan.plan_summary,
            total_tss=totals.get('total_tss'),
            total_distance=str(totals.get('total_distance_km', '')),
            total_duration=str(totals.get('total_duration_hours', '')),
            weeks=weeks,
            workouts=workouts,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            approved_at=plan.approved_at
        )
    
    def _to_list_item_dto(self, plan) -> PlanListItemDTO:
        """Convierte un modelo a DTO de lista."""
        workout_count = 0
        total_tss = None
        
        if plan.plan_data:
            workouts = self.generator.extract_workouts_flat(plan.plan_data)
            workout_count = len(workouts)
            total_tss = plan.plan_data.get('total_tss')
        
        return PlanListItemDTO(
            id=plan.id,
            athlete_id=plan.athlete_id,
            athlete_name=plan.athlete_name,
            status=plan.status,
            weeks_count=plan.weeks,
            start_date=plan.start_date,
            total_tss=total_tss,
            workout_count=workout_count,
            created_at=plan.created_at
        )

