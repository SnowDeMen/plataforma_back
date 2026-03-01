"""
Casos de uso para operaciones de planes de entrenamiento.
Contiene la logica de negocio para generar, aprobar y gestionar planes.
"""
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, date, timedelta
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
    PlanApplyRequestDTO,
    PlanModifyRequestDTO,
    PlanModifyResponseDTO,
    PlanModifyChangeDTO,
    SafeAlternativeDTO,
    SafeAlternativeWorkoutDTO,
    PlanModificationHistoryDTO,
    ModificationHistoryEntryDTO,
    ApplyTPPlanRequestDTO,
    ApplyTPPlanResponseDTO
)
from app.infrastructure.repositories.plan_repository import PlanRepository
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.infrastructure.autogen.plan_generator import PlanGenerator
from app.shared.exceptions.domain import PlanNotFoundException
from app.application.interfaces.trainingpeaks_plan_publisher import TrainingPeaksPlanPublisher

from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.selenium_executor import run_selenium
from app.shared.utils.date_utils import calculate_next_start_date



class PlanUseCases:
    """
    Casos de uso para operaciones de planes de entrenamiento.
    
    Maneja la generacion asincrona de planes, aprobacion/rechazo
    y consulta de planes existentes.
    """
    
    # Almacenamiento temporal de callbacks de progreso por plan_id
    _progress_callbacks: Dict[int, List[Callable[[int, str], None]]] = {}
    # Callbacks de completado por plan_id: (success, message)
    _complete_callbacks: Dict[int, List[Callable[[bool, str], None]]] = {}
    
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
    def register_complete_callback(
        cls,
        plan_id: int,
        callback: Callable[[bool, str], None]
    ) -> None:
        """
        Registra un callback para recibir notificación de completado.

        Args:
            plan_id: ID del plan
            callback: Función que recibe (success, message)
        """
        if plan_id not in cls._complete_callbacks:
            cls._complete_callbacks[plan_id] = []
        cls._complete_callbacks[plan_id].append(callback)

    @classmethod
    def unregister_complete_callback(
        cls,
        plan_id: int,
        callback: Callable[[bool, str], None]
    ) -> None:
        """
        Elimina un callback de completado.

        Args:
            plan_id: ID del plan
            callback: Callback a eliminar
        """
        if plan_id in cls._complete_callbacks:
            try:
                cls._complete_callbacks[plan_id].remove(callback)
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

    @classmethod
    def _notify_complete(cls, plan_id: int, success: bool, message: str) -> None:
        """
        Notifica a todos los callbacks registrados de completado.

        Args:
            plan_id: ID del plan
            success: Si la generación fue exitosa
            message: Mensaje final
        """
        callbacks = cls._complete_callbacks.get(plan_id, [])
        for callback in callbacks:
            try:
                callback(success, message)
            except Exception as e:
                logger.warning(f"Error en callback de completado: {e}")
    
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
        # 0. Limpiar planes incompletos previos (pending/generating)
        await self.repository.delete_incomplete_plans_by_athlete(dto.athlete_id)

        # Extraer performance y computed_metrics
        performance = dto.athlete_info.performance or {}
        computed_metrics = performance.get('computed_metrics') if isinstance(performance, dict) else None
        
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
            'performance': performance,
            'computed_metrics': computed_metrics  # Metricas computadas para contexto LLM
        }
        
        # Log si hay metricas computadas disponibles
        if computed_metrics:
            logger.info(
                f"Plan con metricas computadas: CTL={computed_metrics.get('ctl', 'N/A')}, "
                f"TSB={computed_metrics.get('tsb', 'N/A')}"
            )
        
        # Obtener start_date
        start_date = dto.start_date
        today = datetime.now().date()
        if not start_date or start_date <= today:
            try:
                
                
                athlete_repo = AthleteRepository(self.db)
                athlete = await athlete_repo.get_by_id(dto.athlete_id)
                tp_name = athlete.tp_name if athlete and athlete.tp_name else dto.athlete_name

                def _scrape_start_date():
                    session = None
                    try:
                        session = DriverManager.create_session(f"Date_{tp_name}")
                        session.auth_service.login_with_cookie()
                        date_str = session.athlete_service.get_last_workout_date(tp_name)
                        if date_str:
                            try:
                                dt = datetime.strptime(date_str, "%m/%d/%y")
                                return (dt + timedelta(days=1)).date()
                            except ValueError:
                                try:
                                    dt = datetime.strptime(date_str, "%m/%d/%Y")
                                    return (dt + timedelta(days=1)).date()
                                except ValueError:
                                    return None
                        return None
                    finally:
                        if session:
                            session.close()

                scraped_date = await run_selenium(_scrape_start_date)
                if scraped_date and scraped_date > today:
                    preferred_rest_day = athlete.preferred_rest_day if athlete else None
                    start_date = calculate_next_start_date(scraped_date, preferred_rest_day)
                    logger.info(f"Start date overridden from TP for {tp_name}: {start_date}")
            except Exception as e:
                logger.warning(f"No se pudo extraer la fecha de inicio desde TrainingPeaks: {e}")

        # Si aún no hay start_date válido, fallback as a normal generate
        if not start_date:
            start_date = today

        # Crear plan en BD
        plan = await self.repository.create(
            athlete_id=dto.athlete_id,
            athlete_name=dto.athlete_name,
            athlete_context=athlete_context,
            weeks=dto.weeks,
            start_date=start_date
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
        
        # La generación puede emitir múltiples callbacks de progreso muy rápido.
        # En SQLAlchemy AsyncSession NO se permiten operaciones concurrentes sobre la misma sesión,
        # por lo que serializamos las escrituras/commits con un lock para evitar:
        # "This session is provisioning a new connection; concurrent operations are not permitted".
        progress_lock = asyncio.Lock()

        async def handle_progress(progress: int, message: str) -> None:
            """
            Persiste progreso en BD de forma segura (sin concurrencia en la sesión)
            y notifica callbacks (WebSocket/UI) fuera del lock.
            """
            try:
                async with progress_lock:
                    await self.repository.update_progress(plan_id, progress, message)
                    await self.db.commit()
            except Exception as e:
                # No propagamos: un fallo de progreso no debe tumbar la generación.
                logger.warning(f"Error persistiendo progreso del plan {plan_id}: {e}")
                return

            # Notificar callbacks registrados (WebSocket)
            self._notify_progress(plan_id, progress, message)

            # Llamar callback local si existe
            if on_progress:
                try:
                    on_progress(progress, message)
                except Exception as e:
                    logger.warning(f"Error en callback local de progreso (plan {plan_id}): {e}")

        def schedule_progress_update(progress: int, message: str) -> None:
            """
            Programa la actualización de progreso como task y captura excepciones
            para evitar 'Task exception was never retrieved'.
            """
            task = asyncio.create_task(handle_progress(progress, message))

            def _swallow_task_exception(t: asyncio.Task) -> None:
                try:
                    t.result()
                except Exception as e:
                    logger.warning(f"Task de progreso falló (plan {plan_id}): {e}")

            task.add_done_callback(_swallow_task_exception)
        
        try:
            # Generar plan
            plan_data = await self.generator.generate(
                athlete_context=plan.athlete_context or {},
                start_date=plan.start_date,
                on_progress=schedule_progress_update
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
            final_message = "Plan generado exitosamente"
            await self.repository.update_progress(plan_id, 100, final_message)
            await self.db.commit()

            # Notificar completado (WebSocket/UI)
            self._notify_complete(plan_id, True, final_message)
            
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
            error_text = str(e)
            # Mensaje corto y humano para errores típicos de OpenAI por cuota/billing.
            # Esto evita ensuciar el estado con texto enorme y facilita el diagnóstico.
            if "insufficient_quota" in error_text or "Error code: 429" in error_text:
                error_text = "Error OpenAI: cuota insuficiente (429). Revisa billing/cuota de la API key."
            final_error_message = f"Error: {error_text}"
            await self.repository.update_progress(plan_id, 0, final_error_message)
            await self.db.commit()

            # Notificar completado como fallo (WebSocket/UI)
            self._notify_complete(plan_id, False, final_error_message)
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

    async def approve_and_apply_plan(
        self,
        plan_id: int,
        dto: PlanApplyRequestDTO,
        publisher: Optional[TrainingPeaksPlanPublisher] = None
    ) -> TrainingPlanDTO:
        """
        Aprueba y aplica un plan de entrenamiento en TrainingPeaks.

        Reglas:
        - Flujo determinista y bloqueante (la request espera el resultado).
        - Se levanta una sesion efimera de Selenium para publicar los workouts.
        - Si cualquier paso falla, NO se marca el plan como 'applied'.
        - Usa tp_name del atleta (obtenido via tp_sync) para seleccionarlo en TrainingPeaks.
        """
        plan = await self.repository.get_by_id(plan_id)
        if not plan:
            raise PlanNotFoundException(plan_id)

        if plan.status == "applied":
            raise ValueError("El plan ya fue aplicado anteriormente")

        if not dto.workouts:
            raise ValueError("No se recibieron workouts para aplicar")

        # Obtener el atleta para usar tp_name (nombre exacto en TrainingPeaks)
        athlete_repo = AthleteRepository(self.db)
        athlete = await athlete_repo.get_by_id(plan.athlete_id)
        
        if not athlete:
            logger.error(f"[approve_and_apply] Atleta no encontrado en BD: {plan.athlete_id}")
            raise ValueError(f"Atleta no encontrado: {plan.athlete_id}")
        
        # Log para debugging: mostrar nombre en BD vs nombre en TP
        logger.info(
            f"[approve_and_apply] Atleta encontrado: "
            f"id='{athlete.id}', name='{athlete.name}', tp_name='{athlete.tp_name}'"
        )
        
        if not athlete.tp_name:
            logger.error(
                f"[approve_and_apply] Atleta '{athlete.name}' (id={athlete.id}) "
                "no tiene tp_name configurado. Abortando."
            )
            raise ValueError(
                f"El atleta '{athlete.name}' no tiene tp_name configurado. "
                "Ejecuta la sincronizacion con TrainingPeaks primero."
            )
        
        # Usar tp_name (nombre exacto en TP) en lugar de plan.athlete_name
        tp_athlete_name = athlete.tp_name
        logger.info(f"[approve_and_apply] Usando tp_name para seleccion en TP: '{tp_athlete_name}'")

        if publisher is None:
            from app.infrastructure.trainingpeaks.selenium_plan_publisher import (
                SeleniumTrainingPeaksPlanPublisher,
            )
            publisher = SeleniumTrainingPeaksPlanPublisher()

        try:
            # Publicar en TrainingPeaks (Selenium directo) usando el executor dedicado.
            # run_selenium() usa ThreadPoolExecutor dedicado y semaforo global
            # para limitar operaciones de Selenium concurrentes.
            from app.infrastructure.driver.selenium_executor import run_selenium
            
            await run_selenium(
                publisher.publish_plan,
                plan_id=plan_id,
                athlete_name=tp_athlete_name,
                workouts=dto.workouts,
                start_date=plan.start_date,
                # Por requerimiento, si no se envia carpeta se usa Neuronomy.
                folder_name=dto.folder_name or "Neuronomy",
            )

            # Si no falló, marcar el plan como aplicado.
            now = datetime.utcnow()
            await self.repository.update_status(
                plan_id,
                "applied",
                approved_at=now,
                applied_at=now,
            )
            
            await self.db.commit()

            plan = await self.repository.get_by_id(plan_id)
            logger.info(f"Plan {plan_id} aplicado en TrainingPeaks para atleta '{tp_athlete_name}'")
            return self._to_dto(plan)

        except Exception as e:
            # No cambiamos estado en DB; solo log y propagamos.
            logger.error(f"Error aplicando plan {plan_id} en TrainingPeaks: {e}")
            raise
    
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
            start_time = datetime.utcnow()
            result = await self.generator.modify_plan(
                current_plan=plan.plan_data,
                scope=dto.scope,
                target=dto.target,
                user_prompt=dto.prompt,
                force_apply=dto.force_apply,
                use_safe_alternative=dto.use_safe_alternative
            )
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"[PLAN_MODIFY_USECASE] Generacion completada en {elapsed:.2f}s")
            
            # Verificar si requiere confirmacion
            if result.get('requires_confirmation', False):
                # IMPORTANTE: Persistir el plan aunque requiera confirmacion
                # Esto es para guardar el historial 'warning' (la memoria de la IA)
                if result.get('plan'):
                    await self.repository.update_plan_data(
                        plan_id, 
                        result['plan'], 
                        plan.plan_summary
                    )
                    await self.db.commit()

                # No se aplica el cambio real al contenido, solo se retorna la advertencia
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
            start_totals = datetime.utcnow()
            totals = self.generator.calculate_totals(plan.plan_data)
            elapsed_totals = (datetime.utcnow() - start_totals).total_seconds()
            logger.debug(f"[_to_dto] Totales calculados en {elapsed_totals:.4f}s")
        
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
    
    async def apply_tp_plan(
        self, 
        dto: ApplyTPPlanRequestDTO
    ) -> ApplyTPPlanResponseDTO:
        """
        Aplica un Training Plan existente de TrainingPeaks a un atleta.
        
        Este metodo es para testing del flujo de Selenium que ejecuta
        el TrainingPlanService.apply_training_plan().
        
        Flujo:
        1. Crea sesion de Selenium efimera
        2. Login con cookies
        3. Abre Workout Library
        4. Ejecuta el flujo de aplicar Training Plan
        5. Cierra sesion
        
        Args:
            dto: Datos del plan a aplicar (nombre, atleta, fecha)
            
        Returns:
            ApplyTPPlanResponseDTO con el resultado de la operacion
        """
        from app.infrastructure.driver.driver_manager import DriverManager
        from app.infrastructure.driver.selenium_executor import run_selenium
        
        session = None
        
        try:
            logger.info(
                f"Aplicando TP Plan '{dto.plan_name}' a '{dto.athlete_name}' "
                f"desde {dto.start_date.isoformat()}"
            )
            
            # 1. Crear sesion de Selenium efimera
            session = await run_selenium(
                DriverManager.create_session, 
                dto.athlete_name
            )
            
            # 2. Login con cookies
            logger.info("Login en TrainingPeaks...")
            await run_selenium(session.auth_service.login_with_cookie)
            
            # 3. Abrir Workout Library (para tener el panel activo)
            logger.info("Abriendo Workout Library...")
            await run_selenium(session.workout_service.workout_library)
            
            # 4. Aplicar el Training Plan usando el servicio
            logger.info(f"Aplicando Training Plan: {dto.plan_name}")
            await run_selenium(
                session.training_plan_service.apply_training_plan,
                dto.plan_name,
                dto.athlete_name,
                dto.start_date
            )
            
            logger.info(
                f"Training Plan '{dto.plan_name}' aplicado exitosamente "
                f"a '{dto.athlete_name}'"
            )
            
            return ApplyTPPlanResponseDTO(
                success=True,
                message=f"Plan '{dto.plan_name}' aplicado exitosamente",
                plan_name=dto.plan_name,
                athlete_name=dto.athlete_name,
                start_date=dto.start_date.isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error aplicando TP Plan: {e}")
            return ApplyTPPlanResponseDTO(
                success=False,
                message=f"Error: {str(e)}",
                plan_name=dto.plan_name,
                athlete_name=dto.athlete_name,
                start_date=dto.start_date.isoformat()
            )
            
        finally:
            # 5. Cerrar sesion
            if session:
                try:
                    DriverManager.close_session(session.session_id)
                    logger.info("Sesion de Selenium cerrada")
                except Exception as e:
                    logger.warning(f"Error cerrando sesion: {e}")

