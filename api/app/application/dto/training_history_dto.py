"""
DTOs para sincronización de historial de entrenamientos desde TrainingPeaks.

Este flujo es deliberadamente separado del chat:
- se ejecuta bajo una sesión Selenium existente (`session_id`)
- persiste el resultado como JSON en Postgres
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TrainingHistorySyncRequestDTO(BaseModel):
    """
    Request para iniciar una sincronización de historial.

    Criterios de parada (se evalúan en orden):
    1. Si `from_date` está definido, el barrido se detiene al alcanzar esa fecha.
    2. Si no, se aplica `gap_days`: se detiene tras un hueco continuo sin
       entrenamientos, una vez que ya se encontró al menos 1 día con datos.
    - `timeout` controla esperas internas del scraping (Quick View).
    """
    from_date: Optional[date] = Field(
        None,
        description="Fecha de inicio del rango (inclusive). Si se omite, se usa gap_days como criterio de parada."
    )
    gap_days: int = Field(180, ge=1, le=3650, description="Días consecutivos sin entrenos para cortar la búsqueda")
    timeout: int = Field(12, ge=3, le=120, description="Timeout de extracción por workout (segundos)")

    @field_validator("from_date")
    @classmethod
    def from_date_cannot_be_future(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("from_date no puede ser una fecha futura")
        return v


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


