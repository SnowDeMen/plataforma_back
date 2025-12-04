"""
DTOs relacionados con agentes.
"""
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.shared.constants.agent_constants import AgentType, AgentStatus


class AgentCreateDTO(BaseModel):
    """DTO para crear un agente."""
    
    name: str = Field(..., min_length=1, max_length=255, description="Nombre del agente")
    type: AgentType = Field(..., description="Tipo de agente")
    system_message: Optional[str] = Field(None, description="Mensaje del sistema")
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Configuración adicional")


class AgentUpdateDTO(BaseModel):
    """DTO para actualizar un agente."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    system_message: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    status: Optional[AgentStatus] = None


class AgentResponseDTO(BaseModel):
    """DTO de respuesta para un agente."""
    
    id: int
    name: str
    type: AgentType
    status: AgentStatus
    configuration: Dict[str, Any]
    system_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        """Configuración de Pydantic."""
        from_attributes = True


class AgentListResponseDTO(BaseModel):
    """DTO de respuesta para lista de agentes."""
    
    agents: list[AgentResponseDTO]
    total: int
    skip: int
    limit: int

