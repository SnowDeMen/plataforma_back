"""
Endpoints para operaciones con planes de entrenamiento.
Maneja la generacion, consulta y aprobacion de planes de 4 semanas.
"""
from typing import List, Optional
from datetime import date
import asyncio

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.plan_use_cases import PlanUseCases
from app.shared.exceptions.domain import PlanNotFoundException
from app.application.dto.plan_dto import (
    PlanGenerationRequestDTO,
    TrainingPlanDTO,
    PlanProgressDTO,
    PlanListItemDTO,
    PlanApprovalDTO,
    PlanApplyRequestDTO,
    AthleteInfoDTO,
    PlanModifyRequestDTO,
    PlanModifyResponseDTO,
    PlanModificationHistoryDTO,
    ApplyTPPlanRequestDTO,
    ApplyTPPlanResponseDTO
)
from app.infrastructure.database.session import get_db
from app.infrastructure.repositories.plan_repository import PlanRepository


router = APIRouter(prefix="/plans", tags=["Plans"])


def get_plan_use_cases(db: AsyncSession = Depends(get_db)) -> PlanUseCases:
    """Dependency para obtener instancia de PlanUseCases."""
    return PlanUseCases(db)


@router.post(
    "/generate",
    response_model=TrainingPlanDTO,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generar un nuevo plan de entrenamiento"
)
async def generate_plan(
    dto: PlanGenerationRequestDTO,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> TrainingPlanDTO:
    """
    Inicia la generacion de un plan de entrenamiento de 4 semanas.
    
    El plan se genera en background. Usa el endpoint WebSocket
    /plans/ws/{plan_id} para recibir actualizaciones de progreso.
    
    Args:
        dto: Datos del atleta y configuracion del plan
        background_tasks: Para ejecutar generacion en background
        use_cases: Casos de uso (inyectado)
        
    Returns:
        TrainingPlanDTO con el plan en estado 'generating'
    """
    # Crear plan en BD
    plan = await use_cases.create_plan(dto)
    
    # Generar contenido en background.
    #
    # Nota importante (Docker/Uvicorn + asyncpg):
    # NO usamos asyncio.run() aquí porque crea un event loop nuevo. SQLAlchemy async/asyncpg
    # mantienen conexiones/pool ligados al event loop actual; si se ejecuta en otro loop se
    # provoca: "got Future attached to a different loop" y errores al terminar conexiones.
    #
    # Por eso, programamos la tarea en el MISMO loop de la request con asyncio.create_task().
    async def _generate_in_background(plan_id: int) -> None:
        """Tarea async de generación con su propia sesión de BD."""
        from app.infrastructure.database.session import AsyncSessionLocal
        from loguru import logger

        async with AsyncSessionLocal() as db:
            try:
                bg_use_cases = PlanUseCases(db)
                await bg_use_cases.generate_plan(plan_id)
            except Exception as e:
                # PlanUseCases.generate_plan ya intenta persistir estado/progreso de error en BD.
                logger.error(f"Error en generacion background (plan_id={plan_id}): {e}")

    task = asyncio.create_task(_generate_in_background(plan.id))

    def _log_task_exception(t: asyncio.Task) -> None:
        """Evita que excepciones del background task se pierdan silenciosamente."""
        try:
            t.result()
        except Exception as e:
            from loguru import logger
            logger.error(f"Tarea de generacion falló (plan_id={plan.id}): {e}")

    task.add_done_callback(_log_task_exception)
    
    return plan


@router.post(
    "/generate-sync",
    response_model=TrainingPlanDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Generar plan de forma sincrona (para testing)"
)
async def generate_plan_sync(
    dto: PlanGenerationRequestDTO,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> TrainingPlanDTO:
    """
    Genera un plan de entrenamiento de forma sincrona.
    
    Util para testing. Para produccion, usar el endpoint
    asincrono /generate.
    
    Args:
        dto: Datos del atleta y configuracion
        use_cases: Casos de uso (inyectado)
        
    Returns:
        TrainingPlanDTO con el plan generado
    """
    return await use_cases.create_and_generate(dto)


@router.get(
    "/{plan_id}",
    response_model=TrainingPlanDTO,
    summary="Obtener un plan de entrenamiento"
)
async def get_plan(
    plan_id: int,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> TrainingPlanDTO:
    """
    Obtiene un plan de entrenamiento por ID.
    
    Args:
        plan_id: ID del plan
        use_cases: Casos de uso (inyectado)
        
    Returns:
        TrainingPlanDTO completo
        
    Raises:
        404: Si el plan no existe
    """
    try:
        return await use_cases.get_plan(plan_id)
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{plan_id}/progress",
    response_model=PlanProgressDTO,
    summary="Obtener progreso de generacion"
)
async def get_plan_progress(
    plan_id: int,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> PlanProgressDTO:
    """
    Obtiene el estado de progreso de generacion de un plan.
    
    Args:
        plan_id: ID del plan
        use_cases: Casos de uso (inyectado)
        
    Returns:
        PlanProgressDTO con el estado actual
        
    Raises:
        404: Si el plan no existe
    """
    try:
        return await use_cases.get_plan_progress(plan_id)
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{plan_id}/approve",
    response_model=TrainingPlanDTO,
    summary="Aprobar un plan de entrenamiento"
)
async def approve_plan(
    plan_id: int,
    dto: Optional[PlanApprovalDTO] = None,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> TrainingPlanDTO:
    """
    Aprueba un plan de entrenamiento.
    
    Cambia el estado a 'active' para indicar que el coach
    ha validado el plan y esta listo para el atleta.
    
    Args:
        plan_id: ID del plan
        dto: Datos de aprobacion opcionales
        use_cases: Casos de uso (inyectado)
        
    Returns:
        TrainingPlanDTO actualizado
        
    Raises:
        404: Si el plan no existe
    """
    try:
        return await use_cases.approve_plan(plan_id, dto)
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/{plan_id}/approve-and-apply",
    response_model=TrainingPlanDTO,
    summary="Aprobar y aplicar un plan de entrenamiento en TrainingPeaks (Selenium directo)"
)
async def approve_and_apply_plan(
    plan_id: int,
    dto: PlanApplyRequestDTO,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> TrainingPlanDTO:
    """
    Aprueba y aplica un plan de entrenamiento a TrainingPeaks.

    Reglas del flujo:
    - Crea una sesión efímera de Selenium, hace login con cookies y selecciona atleta.
    - Crea workouts en Workout Library y los arrastra al calendario en las fechas del plan.
    - Si todo sale bien, marca el plan como 'applied'.
    """
    try:
        return await use_cases.approve_and_apply_plan(plan_id, dto)
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # Evitamos exponer detalles internos del driver; el log ya captura el traceback.
        raise HTTPException(status_code=500, detail="Error al aplicar el plan a TrainingPeaks")


@router.post(
    "/{plan_id}/reject",
    response_model=TrainingPlanDTO,
    summary="Rechazar un plan de entrenamiento"
)
async def reject_plan(
    plan_id: int,
    dto: Optional[PlanApprovalDTO] = None,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> TrainingPlanDTO:
    """
    Rechaza un plan de entrenamiento.
    
    El plan se marca como 'rejected' y se puede regenerar.
    
    Args:
        plan_id: ID del plan
        dto: Datos de rechazo con feedback opcional
        use_cases: Casos de uso (inyectado)
        
    Returns:
        TrainingPlanDTO actualizado
        
    Raises:
        404: Si el plan no existe
    """
    try:
        return await use_cases.reject_plan(plan_id, dto)
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un plan de entrenamiento"
)
async def delete_plan(
    plan_id: int,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> None:
    """
    Elimina un plan de entrenamiento.
    
    Args:
        plan_id: ID del plan
        use_cases: Casos de uso (inyectado)
        
    Raises:
        404: Si el plan no existe
    """
    deleted = await use_cases.delete_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} no encontrado")


@router.put(
    "/{plan_id}/modify",
    response_model=PlanModifyResponseDTO,
    summary="Modificar un plan de entrenamiento via chat"
)
async def modify_plan(
    plan_id: int,
    dto: PlanModifyRequestDTO,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> PlanModifyResponseDTO:
    """
    Modifica un plan de entrenamiento existente usando IA.
    
    Permite modificar un dia, una semana, o el plan completo
    basandose en las instrucciones del usuario y el contexto
    original del plan (incluyendo justificaciones CoT).
    
    Args:
        plan_id: ID del plan a modificar
        dto: Datos de la modificacion (scope, target, prompt)
        use_cases: Casos de uso (inyectado)
        
    Returns:
        PlanModifyResponseDTO con el plan actualizado y resumen de cambios
        
    Raises:
        404: Si el plan no existe
        400: Si el scope no es valido
    """
    # Validar scope
    valid_scopes = ['day', 'week', 'plan']
    if dto.scope not in valid_scopes:
        raise HTTPException(
            status_code=400, 
            detail=f"Scope invalido. Debe ser uno de: {valid_scopes}"
        )
    
    try:
        return await use_cases.modify_plan(plan_id, dto)
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        from loguru import logger
        logger.error(f"Error modificando plan {plan_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Error al procesar la modificacion del plan"
        )


@router.get(
    "/athlete/{athlete_id}",
    response_model=List[PlanListItemDTO],
    summary="Obtener planes de un atleta"
)
async def get_athlete_plans(
    athlete_id: str,
    status_filter: Optional[str] = None,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> List[PlanListItemDTO]:
    """
    Obtiene todos los planes de un atleta.
    
    Args:
        athlete_id: ID del atleta
        status_filter: Filtrar por estado (opcional)
        use_cases: Casos de uso (inyectado)
        
    Returns:
        Lista de PlanListItemDTO
    """
    return await use_cases.get_athlete_plans(athlete_id, status_filter)


@router.get(
    "/",
    response_model=List[PlanListItemDTO],
    summary="Listar planes por estado"
)
async def list_plans(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> List[PlanListItemDTO]:
    """
    Lista todos los planes, opcionalmente filtrados por estado.
    
    Args:
        status_filter: Filtrar por estado (pending, generating, review, active, applied)
        db: Sesion de BD (inyectado)
        
    Returns:
        Lista de PlanListItemDTO
    """
    use_cases = PlanUseCases(db)
    
    if status_filter:
        return await use_cases.get_plans_by_status(status_filter)
    
    # Obtener todos
    repository = PlanRepository(db)
    plans = await repository.get_all()
    
    return [use_cases._to_list_item_dto(p) for p in plans]


@router.get(
    "/{plan_id}/history",
    response_model=PlanModificationHistoryDTO,
    summary="Obtener historial de modificaciones de un plan"
)
async def get_plan_history(
    plan_id: int,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> PlanModificationHistoryDTO:
    """
    Obtiene el historial de todas las modificaciones realizadas a un plan.
    
    Incluye:
    - Todas las modificaciones con timestamps
    - Decisiones tomadas (directa, forzada, alternativa)
    - Advertencias de riesgo emitidas
    - Prompts originales del usuario
    
    Args:
        plan_id: ID del plan
        use_cases: Casos de uso (inyectado)
        
    Returns:
        PlanModificationHistoryDTO con el historial completo
        
    Raises:
        404: Si el plan no existe
    """
    try:
        return await use_cases.get_modification_history(plan_id)
    except PlanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/apply-tp-plan",
    response_model=ApplyTPPlanResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Aplicar un Training Plan existente de TrainingPeaks a un atleta"
)
async def apply_tp_plan(
    dto: ApplyTPPlanRequestDTO,
    use_cases: PlanUseCases = Depends(get_plan_use_cases)
) -> ApplyTPPlanResponseDTO:
    """
    Aplica un Training Plan existente en TrainingPeaks a un atleta.
    
    Este endpoint es para testing del flujo de Selenium que ejecuta
    el TrainingPlanService.apply_training_plan().
    
    Flujo:
    1. Crea sesion de Selenium efimera
    2. Login con cookies
    3. Abre Workout Library
    4. Ejecuta el flujo de aplicar Training Plan
    5. Cierra sesion
    
    Args:
        dto: Datos del plan a aplicar (nombre, atleta, fecha)
        use_cases: Casos de uso (inyectado)
        
    Returns:
        ApplyTPPlanResponseDTO con el resultado de la operacion
    """
    try:
        return await use_cases.apply_tp_plan(dto)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        from loguru import logger
        logger.error(f"Error aplicando TP Plan: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error al aplicar el Training Plan: {str(e)}"
        )
