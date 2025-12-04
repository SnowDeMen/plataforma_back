"""
Entidad de dominio: Conversation (Conversación).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.shared.constants.agent_constants import ConversationStatus


@dataclass
class Message:
    """Representa un mensaje en una conversación."""
    
    sender: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """
    Entidad de dominio que representa una conversación entre agentes.
    """
    
    id: Optional[int] = None
    title: str = ""
    status: ConversationStatus = ConversationStatus.ACTIVE
    agent_ids: List[int] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validaciones después de la inicialización."""
        if not self.title:
            raise ValueError("El título de la conversación no puede estar vacío")
        if len(self.agent_ids) < 2:
            raise ValueError("Una conversación requiere al menos 2 agentes")
    
    def add_message(self, sender: str, content: str, metadata: Optional[Dict] = None) -> None:
        """
        Añade un mensaje a la conversación.
        
        Args:
            sender: Nombre del remitente
            content: Contenido del mensaje
            metadata: Metadatos adicionales del mensaje
        """
        message = Message(
            sender=sender,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )
        self.messages.append(message)
    
    def complete(self) -> None:
        """Marca la conversación como completada."""
        self.status = ConversationStatus.COMPLETED
        self.completed_at = datetime.utcnow()
    
    def cancel(self) -> None:
        """Cancela la conversación."""
        self.status = ConversationStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def set_error(self) -> None:
        """Marca la conversación en estado de error."""
        self.status = ConversationStatus.ERROR
    
    def get_message_count(self) -> int:
        """
        Obtiene el número de mensajes en la conversación.
        
        Returns:
            int: Cantidad de mensajes
        """
        return len(self.messages)
    
    def is_active(self) -> bool:
        """
        Verifica si la conversación está activa.
        
        Returns:
            bool: True si está activa, False en caso contrario
        """
        return self.status == ConversationStatus.ACTIVE

