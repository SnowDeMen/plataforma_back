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
    athlete_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Informacion adicional del atleta para contexto del agente"
    )


class SessionResponseDTO(BaseModel):
    """DTO de respuesta para una sesión de entrenamiento."""
    
    session_id: str = Field(..., description="Identificador único de la sesión")
    athlete_name: str = Field(..., description="Nombre del atleta")
    status: SessionStatus = Field(..., description="Estado de la sesión")
    driver_active: bool = Field(..., description="Indica si el driver de Selenium está activo")
    created_at: datetime = Field(..., description="Fecha y hora de creación")
    message: Optional[str] = Field(None, description="Mensaje adicional")

    class Config:
        """Configuración de Pydantic."""
        from_attributes = True

