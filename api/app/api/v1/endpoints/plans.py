"""
Endpoints para operaciones con planes de entrenamiento.
Maneja la generacion, consulta y aprobacion de planes de 4 semanas.
"""
from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.plan_use_cases import PlanUseCases
from app.shared.exceptions.domain import PlanNotFoundException
from app.application.dto.plan_dto import (
    PlanGenerationRequestDTO,
    TrainingPlanDTO,
    PlanProgressDTO,
    PlanListItemDTO,
    PlanApprovalDTO,
    AthleteInfoDTO,
    PlanModifyRequestDTO,
    PlanModifyResponseDTO,
    PlanModificationHistoryDTO
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
    background_tasks: BackgroundTasks,
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
    
    # Generar contenido en background
    async def generate_in_background(plan_id: int):
        """Tarea de generacion en background."""
        # Crear nueva sesion de BD para el background task
        from app.infrastructure.database.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as db:
            try:
                bg_use_cases = PlanUseCases(db)
                await bg_use_cases.generate_plan(plan_id)
            except Exception as e:
                from loguru import logger
                logger.error(f"Error en generacion background: {e}")
    
    # Agregar tarea al background
    background_tasks.add_task(generate_in_background, plan.id)
    
    # Actualizar estado a generating antes de retornar
    plan.status = "generating"
    
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
