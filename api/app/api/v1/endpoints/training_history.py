"""
Endpoints para sincronización del historial de entrenamientos (TrainingPeaks).

Este flujo es separado del chat y está orientado a:
- extraer historial completo (o lo más completo posible) vía Selenium/MCP
- persistirlo en la base de datos como JSON (AthleteModel.performance.training_history)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dto.training_history_dto import (
    TrainingHistoryJobStatusDTO,
    TrainingHistorySyncRequestDTO,
    TrainingHistorySyncResponseDTO,
)
from app.application.use_cases.training_history_use_cases import TrainingHistoryUseCases
from app.api.v1.dependencies.use_case_deps import get_training_history_use_cases


router = APIRouter(prefix="/athletes/{athlete_id}/training-history", tags=["Training History"])


@router.post(
    "/sync",
    response_model=TrainingHistorySyncResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Iniciar sincronización del historial de entrenamientos"
)
async def start_training_history_sync(
    athlete_id: str,
    dto: TrainingHistorySyncRequestDTO,
    use_cases: TrainingHistoryUseCases = Depends(get_training_history_use_cases),
) -> TrainingHistorySyncResponseDTO:
    """
    Inicia un job asíncrono que recorre el calendario de TrainingPeaks hacia atrás,
    extrae workouts (Quick View) y persiste el resultado en DB como JSON.
    """
    return await use_cases.start_sync(athlete_id=athlete_id, dto=dto)


@router.get(
    "/jobs/{job_id}",
    response_model=TrainingHistoryJobStatusDTO,
    summary="Obtener estado de un job de historial (polling)"
)
async def get_training_history_job_status(
    athlete_id: str,
    job_id: str,
    use_cases: TrainingHistoryUseCases = Depends(get_training_history_use_cases),
) -> TrainingHistoryJobStatusDTO:
    """
    Retorna el estado actual del job. Ideal para polling desde frontend.
    """
    try:
        return await use_cases.get_job_status(athlete_id=athlete_id, job_id=job_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no encontrado")


