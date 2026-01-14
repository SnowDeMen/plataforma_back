"""
DTOs para sincronización de historial de entrenamientos desde TrainingPeaks.

Este flujo es deliberadamente separado del chat:
- se ejecuta bajo una sesión Selenium existente (`session_id`)
- persiste el resultado como JSON en Postgres
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrainingHistorySyncRequestDTO(BaseModel):
    """
    Request para iniciar una sincronización de historial.

    Notas:
    - `gap_days` define el corte hacia atrás: se detiene tras encontrar un hueco
      continuo sin entrenamientos, una vez que ya se encontró al menos 1 día con datos.
    - `timeout` controla esperas internas del scraping (Quick View).
    """
    gap_days: int = Field(180, ge=1, le=3650, description="Días consecutivos sin entrenos para cortar la búsqueda")
    timeout: int = Field(12, ge=3, le=120, description="Timeout de extracción por workout (segundos)")


class TrainingHistorySyncResponseDTO(BaseModel):
    """Respuesta inmediata al iniciar un job."""

    job_id: str
    status: str
    progress: int
    message: str
    created_at: datetime


class TrainingHistoryJobStatusDTO(BaseModel):
    """Estado actual del job (polling)."""

    job_id: str
    status: str
    progress: int
    message: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


