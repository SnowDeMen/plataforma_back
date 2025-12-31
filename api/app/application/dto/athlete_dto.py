"""
DTOs relacionados con atletas.
Definen la estructura de datos para transferir informacion de atletas.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AthleteDTO(BaseModel):
    """
    DTO para representar un atleta sincronizado de Airtable.
    Mapea la estructura anidada que espera el frontend.
    """
    id: str = Field(..., description="ID del registro de Airtable")
    airtable_id: Optional[str] = Field(None, description="ID del registro de Airtable (redundante)")
    name: str = Field(..., description="Nombre completo del atleta")
    email: Optional[str] = Field(None, description="Email del atleta")
    status: str = Field(..., description="Estado del atleta (Plan activo, etc)")
    
    # Campos principales
    discipline: Optional[str] = None
    level: Optional[str] = None
    goal: Optional[str] = None
    age: Optional[int] = None
    experience: Optional[str] = None
    
    # Estructuras complejas (JSON)
    personal: Optional[Dict[str, Any]] = None
    medica: Optional[Dict[str, Any]] = None
    deportiva: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
