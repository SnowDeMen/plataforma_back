"""
Endpoints REST para gestion de atletas.

Proporciona operaciones CRUD para atletas,
incluyendo listado, consulta, actualizacion, cambio de status,
metricas computadas y alertas.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from loguru import logger

from app.application.use_cases.athlete_use_cases import AthleteUseCases, AthleteNotFoundException
from app.application.dto.athlete_dto import (
    AthleteDTO,
    AthleteListItemDTO,
    AthleteUpdateDTO,
    AthleteStatusUpdateDTO,
    AthleteCreateDTO
)
from app.application.dto.metrics_dto import (
    ComputedMetricsDTO,
    AlertDTO,
    AlertsListResponseDTO,
    MetricsRecomputeResponseDTO
)
from app.api.v1.dependencies.use_case_deps import get_athlete_use_cases
from app.infrastructure.database.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.repositories.athlete_repository import AthleteRepository


router = APIRouter(prefix="/athletes", tags=["Athletes"])


@router.get(
    "",
    response_model=List[AthleteListItemDTO],
    summary="Listar atletas con filtros opcionales"
)
async def list_athletes(
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por status"),
    discipline: Optional[str] = Query(None, description="Filtrar por disciplina"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de resultados"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginacion"),
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
) -> List[AthleteListItemDTO]:
    """
    Lista todos los atletas con filtros opcionales.
    
    - **status**: Filtrar por status (Por generar, Por revisar, Plan activo)
    - **discipline**: Filtrar por disciplina
    - **limit**: Numero maximo de resultados
    - **offset**: Desplazamiento para paginacion
    """
    return await use_cases.list_athletes(
        status=status_filter,
        discipline=discipline,
        limit=limit,
        offset=offset
    )


@router.get(
    "/counts",
    response_model=Dict[str, int],
    summary="Obtener conteo de atletas por status"
)
async def get_status_counts(
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
) -> Dict[str, int]:
    """
    Obtiene el conteo de atletas agrupados por status.
    
    Retorna un diccionario con los conteos:
    - Por generar
    - Por revisar
    - Plan activo
    """
    return await use_cases.get_status_counts()


@router.get(
    "/{athlete_id}",
    response_model=AthleteDTO,
    summary="Obtener detalle de un atleta"
)
async def get_athlete(
    athlete_id: str,
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
) -> AthleteDTO:
    """
    Obtiene el detalle completo de un atleta por su ID.
    
    Incluye toda la informacion: personal, medica, deportiva y performance.
    """
    try:
        return await use_cases.get_athlete(athlete_id)
    except AthleteNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{athlete_id}/training-history",
    response_model=Dict[str, Any],
    summary="Obtener historial sincronizado (training_history) de un atleta"
)
async def get_training_history(
    athlete_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Retorna el documento JSON persistido en `AthleteModel.performance.training_history`.
    
    Nota:
    - Este endpoint existe porque el DTO `AthleteDTO.performance` está tipado como
      `PerformanceSummaryDTO` y no garantiza transportar llaves arbitrarias.
    """
    repo = AthleteRepository(db)
    athlete = await repo.get_by_id(athlete_id)
    if not athlete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atleta no encontrado")
    
    performance = athlete.performance if isinstance(athlete.performance, dict) else {}
    training_history = performance.get("training_history") if isinstance(performance, dict) else None
    
    if not training_history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Historial no disponible. Primero sincroniza el historial.")
    
    # Se retorna tal cual fue persistido.
    return training_history


@router.put(
    "/{athlete_id}",
    response_model=AthleteDTO,
    summary="Actualizar datos de un atleta"
)
async def update_athlete(
    athlete_id: str,
    dto: AthleteUpdateDTO,
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
) -> AthleteDTO:
    """
    Actualiza los datos de un atleta existente.
    
    Solo se actualizan los campos proporcionados en el body.
    Los campos no incluidos o con valor null se mantienen sin cambios.
    """
    try:
        return await use_cases.update_athlete(athlete_id, dto)
    except AthleteNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/{athlete_id}/status",
    response_model=AthleteDTO,
    summary="Cambiar status de un atleta"
)
async def update_athlete_status(
    athlete_id: str,
    dto: AthleteStatusUpdateDTO,
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
) -> AthleteDTO:
    """
    Actualiza solo el status de un atleta.
    
    Status validos:
    - Por generar
    - Por revisar
    - Plan activo
    """
    try:
        return await use_cases.update_status(athlete_id, dto)
    except AthleteNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "",
    response_model=AthleteDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo atleta"
)
async def create_athlete(
    dto: AthleteCreateDTO,
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
) -> AthleteDTO:
    """
    Crea un nuevo atleta en la base de datos.
    """
    return await use_cases.create_athlete(dto)


@router.delete(
    "/{athlete_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un atleta"
)
async def delete_athlete(
    athlete_id: str,
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
):
    """
    Elimina un atleta de la base de datos.
    """
    try:
        await use_cases.delete_athlete(athlete_id)
    except AthleteNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/seed",
    response_model=Dict[str, Any],
    summary="Cargar datos iniciales de atletas"
)
async def seed_athletes(
    athletes_data: List[Dict[str, Any]],
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
) -> Dict[str, Any]:
    """
    Carga masiva de atletas desde datos externos.
    
    Acepta una lista de objetos atleta y los inserta o actualiza
    en la base de datos (upsert).
    
    Util para sincronizar datos desde fuentes externas como
    TrainingPeaks o archivos CSV.
    """
    return await use_cases.seed_athletes(athletes_data)


# =============================================================================
# ENDPOINTS DE METRICAS Y ALERTAS
# =============================================================================


@router.get(
    "/{athlete_id}/metrics",
    response_model=ComputedMetricsDTO,
    summary="Obtener metricas computadas del atleta"
)
async def get_athlete_metrics(
    athlete_id: str,
    db: AsyncSession = Depends(get_db)
) -> ComputedMetricsDTO:
    """
    Obtiene las metricas computadas del historial de entrenamiento.
    
    Incluye:
    - Carga de entrenamiento (CTL, ATL, TSB, Ramp Rate)
    - Adherencia y consistencia
    - Distribucion de intensidad
    - Tendencias y patrones
    - Alertas activas
    
    Las metricas se computan automaticamente al sincronizar el historial.
    """
    repo = AthleteRepository(db)
    athlete = await repo.get_by_id(athlete_id)
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Atleta no encontrado"
        )
    
    performance = athlete.performance if isinstance(athlete.performance, dict) else {}
    computed_metrics = performance.get("computed_metrics")
    
    if not computed_metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Metricas no disponibles. Sincroniza el historial de entrenamientos primero."
        )
    
    # Agregar alertas activas al response
    active_alerts = performance.get("active_alerts", [])
    alerts_dto = [
        AlertDTO(**alert) for alert in active_alerts
    ]
    
    # Construir response
    metrics_response = ComputedMetricsDTO(**computed_metrics)
    metrics_response.active_alerts = alerts_dto
    
    return metrics_response


@router.get(
    "/{athlete_id}/alerts",
    response_model=AlertsListResponseDTO,
    summary="Obtener alertas activas del atleta"
)
async def get_athlete_alerts(
    athlete_id: str,
    category: Optional[str] = Query(
        None, 
        description="Filtrar por categoria: load, recovery, adherence, performance, health"
    ),
    severity: Optional[str] = Query(
        None, 
        description="Filtrar por severidad: info, warning, critical"
    ),
    db: AsyncSession = Depends(get_db)
) -> AlertsListResponseDTO:
    """
    Obtiene las alertas activas del atleta.
    
    Las alertas se generan automaticamente basadas en las metricas
    computadas del historial de entrenamiento.
    
    Categorias:
    - load: Carga de entrenamiento (ramp rate alto, etc)
    - recovery: Recuperacion (TSB muy negativo)
    - adherence: Adherencia al plan (baja adherencia)
    - performance: Rendimiento (distribucion no polarizada)
    - health: Salud (futuro: HRV, sueno)
    
    Severidades:
    - info: Informativo
    - warning: Requiere atencion
    - critical: Accion inmediata requerida
    """
    repo = AthleteRepository(db)
    athlete = await repo.get_by_id(athlete_id)
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Atleta no encontrado"
        )
    
    performance = athlete.performance if isinstance(athlete.performance, dict) else {}
    active_alerts = performance.get("active_alerts", [])
    
    # Aplicar filtros
    filtered_alerts = active_alerts
    filters_applied = {}
    
    if category:
        filtered_alerts = [
            a for a in filtered_alerts 
            if a.get("category") == category
        ]
        filters_applied["category"] = category
    
    if severity:
        filtered_alerts = [
            a for a in filtered_alerts 
            if a.get("severity") == severity
        ]
        filters_applied["severity"] = severity
    
    # Convertir a DTOs
    alerts_dto = [AlertDTO(**alert) for alert in filtered_alerts]
    
    return AlertsListResponseDTO(
        athlete_id=athlete_id,
        total_alerts=len(alerts_dto),
        alerts=alerts_dto,
        filters_applied=filters_applied
    )


@router.post(
    "/{athlete_id}/metrics/recompute",
    response_model=MetricsRecomputeResponseDTO,
    summary="Recomputar metricas del atleta"
)
async def recompute_athlete_metrics(
    athlete_id: str,
    period_days: int = Query(90, ge=7, le=365, description="Dias de historial a analizar"),
    db: AsyncSession = Depends(get_db)
) -> MetricsRecomputeResponseDTO:
    """
    Fuerza el recalculo de metricas y alertas.
    
    Util cuando:
    - Se quiere analizar un periodo diferente
    - Se agregaron nuevas reglas de alerta
    - Se corrigieron datos del historial manualmente
    
    El recalculo usa el historial ya sincronizado en la DB,
    NO requiere re-sincronizar desde TrainingPeaks.
    """
    repo = AthleteRepository(db)
    athlete = await repo.get_by_id(athlete_id)
    
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Atleta no encontrado"
        )
    
    performance = athlete.performance if isinstance(athlete.performance, dict) else {}
    training_history = performance.get("training_history", {})
    days = training_history.get("days", {})
    
    if not days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay historial de entrenamientos sincronizado. Sincroniza primero."
        )
    
    # Computar metricas
    from app.application.services.history_processor import HistoryProcessor
    
    processor = HistoryProcessor()
    metrics = processor.process(days, period_days=period_days)
    
    # Actualizar en DB
    performance["computed_metrics"] = metrics.to_dict()
    performance["active_alerts"] = [alert.to_dict() for alert in metrics.active_alerts]
    
    await repo.update(athlete_id, {"performance": performance})
    await db.commit()
    
    logger.info(
        f"Metricas recomputadas para atleta {athlete_id}: "
        f"CTL={metrics.ctl:.1f}, TSB={metrics.tsb:.1f}, "
        f"alertas={len(metrics.active_alerts)}"
    )
    
    return MetricsRecomputeResponseDTO(
        success=True,
        message=f"Metricas recomputadas exitosamente para {period_days} dias",
        athlete_id=athlete_id,
        computed_at=datetime.utcnow(),
        alerts_count=len(metrics.active_alerts)
    )
