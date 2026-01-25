"""
DTOs relacionados con sesiones de entrenamiento.
Definen la estructura de datos para iniciar y gestionar sesiones.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.shared.constants.session_constants import SessionStatus


class SessionStartDTO(BaseModel):
    """DTO para iniciar una sesión de entrenamiento."""
    
    athlete_name: str = Field(
        ..., 
        min_length=1, 
        max_length=255, 
        description="Nombre del atleta"
    )
    athlete_id: Optional[str] = Field(
        None,
        description="ID del atleta (opcional, preferido sobre nombre)"
    )
    athlete_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Informacion adicional del atleta para contexto del agente"
    )


class SessionResponseDTO(BaseModel):
    """DTO de respuesta para una sesión de entrenamiento."""
    
    session_id: str = Field(..., description="Identificador único de la sesión")
    athlete_id: Optional[str] = Field(None, description="ID del atleta")
    athlete_name: str = Field(..., description="Nombre del atleta")
    status: SessionStatus = Field(..., description="Estado de la sesión")
    driver_active: bool = Field(..., description="Indica si el driver de Selenium está activo")
    created_at: datetime = Field(..., description="Fecha y hora de creación")
    message: Optional[str] = Field(None, description="Mensaje adicional")

    class Config:
        """Configuración de Pydantic."""
        from_attributes = True


class TPSyncResultDTO(BaseModel):
    """
    DTO para el resultado de sincronizacion de atleta con TrainingPeaks.
    
    Se usa para verificar que un atleta existe en TrainingPeaks
    y obtener su nombre de display.
    """
    
    success: bool = Field(..., description="Indica si la sincronizacion fue exitosa")
    username: Optional[str] = Field(None, description="Username/nombre buscado en TrainingPeaks")
    tp_name: Optional[str] = Field(None, description="Nombre del atleta encontrado en TrainingPeaks")
    group: Optional[str] = Field(None, description="Grupo/carpeta donde se encontro el atleta")
    message: Optional[str] = Field(None, description="Mensaje descriptivo del resultado")


class TPSyncJobResponseDTO(BaseModel):
    """
    DTO de respuesta inmediata al iniciar un job de sincronizacion TP.
    
    El endpoint retorna esto inmediatamente y el trabajo continua en background.
    El frontend debe hacer polling al endpoint de status usando el job_id.
    """
    
    job_id: str = Field(..., description="ID unico del job para polling")
    status: str = Field(..., description="Estado del job: running, completed, failed")
    progress: int = Field(..., ge=0, le=100, description="Progreso del job (0-100)")
    message: str = Field(..., description="Mensaje descriptivo del estado actual")
    created_at: datetime = Field(..., description="Fecha y hora de creacion del job")


class TPSyncJobStatusDTO(BaseModel):
    """
    DTO para el estado actual de un job de sincronizacion TP (polling).
    
    Incluye campos adicionales cuando el job esta completado:
    - tp_name: nombre encontrado en TrainingPeaks
    - group: grupo donde se encontro el atleta
    """
    
    job_id: str = Field(..., description="ID unico del job")
    status: str = Field(..., description="Estado: running, completed, failed")
    progress: int = Field(..., ge=0, le=100, description="Progreso del job (0-100)")
    message: str = Field(..., description="Mensaje descriptivo del estado actual")
    created_at: datetime = Field(..., description="Fecha y hora de creacion")
    updated_at: datetime = Field(..., description="Fecha y hora de ultima actualizacion")
    completed_at: Optional[datetime] = Field(None, description="Fecha y hora de finalizacion")
    error: Optional[str] = Field(None, description="Mensaje de error si fallo")
    # Resultado cuando completed
    tp_name: Optional[str] = Field(None, description="Nombre encontrado en TrainingPeaks")
    group: Optional[str] = Field(None, description="Grupo donde se encontro el atleta")

