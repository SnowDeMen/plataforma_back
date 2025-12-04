"""
DTOs relacionados con operaciones de chat.
Definen la estructura de datos para mensajes y respuestas del chat.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ChatMessageDTO(BaseModel):
    """DTO para un mensaje individual de chat."""
    
    role: str = Field(..., description="Rol del mensaje: 'user' o 'assistant'")
    content: str = Field(..., description="Contenido del mensaje")
    timestamp: Optional[str] = Field(None, description="Marca de tiempo del mensaje")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Metadatos adicionales del mensaje"
    )

    class Config:
        from_attributes = True


class ChatRequestDTO(BaseModel):
    """DTO para enviar un mensaje al chat."""
    
    message: str = Field(
        ..., 
        min_length=1,
        max_length=10000,
        description="Mensaje del usuario"
    )


class ChatResponseDTO(BaseModel):
    """DTO de respuesta del chat con el mensaje del agente."""
    
    session_id: str = Field(..., description="ID de la sesion de chat")
    message: str = Field(..., description="Respuesta del agente")
    agent_name: str = Field(..., description="Nombre del agente que respondio")
    timestamp: str = Field(..., description="Marca de tiempo de la respuesta")
    history_length: int = Field(..., description="Cantidad de mensajes en el historial")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Metadatos adicionales de la respuesta"
    )

    class Config:
        from_attributes = True


class ChatHistoryDTO(BaseModel):
    """DTO para el historial completo de una sesion de chat."""
    
    session_id: str = Field(..., description="ID de la sesion")
    athlete_name: str = Field(..., description="Nombre del atleta")
    messages: List[ChatMessageDTO] = Field(
        default_factory=list, 
        description="Lista de mensajes del historial"
    )
    is_active: bool = Field(..., description="Indica si la sesion esta activa")
    created_at: Optional[datetime] = Field(None, description="Fecha de creacion")
    updated_at: Optional[datetime] = Field(None, description="Ultima actualizacion")

    class Config:
        from_attributes = True


class ChatSessionInfoDTO(BaseModel):
    """DTO con informacion resumida de una sesion de chat."""
    
    session_id: str = Field(..., description="ID de la sesion")
    athlete_name: str = Field(..., description="Nombre del atleta")
    message_count: int = Field(..., description="Cantidad de mensajes")
    is_active: bool = Field(..., description="Estado activo de la sesion")
    last_message: Optional[str] = Field(None, description="Ultimo mensaje (resumen)")
    created_at: Optional[datetime] = Field(None, description="Fecha de creacion")
    updated_at: Optional[datetime] = Field(None, description="Ultima actualizacion")

    class Config:
        from_attributes = True


class ChatConfigUpdateDTO(BaseModel):
    """DTO para actualizar la configuracion del chat."""
    
    system_message: Optional[str] = Field(
        None, 
        description="Nuevo mensaje de sistema para el agente"
    )


