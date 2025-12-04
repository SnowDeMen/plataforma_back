"""
Entidad de dominio: Agent (Agente).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any

from app.shared.constants.agent_constants import AgentType, AgentStatus


@dataclass
class Agent:
    """
    Entidad de dominio que representa un agente de AutoGen.
    Contiene la lógica de negocio relacionada con agentes.
    """
    
    id: Optional[int] = None
    name: str = ""
    type: AgentType = AgentType.ASSISTANT
    status: AgentStatus = AgentStatus.IDLE
    configuration: Dict[str, Any] = field(default_factory=dict)
    system_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validaciones después de la inicialización."""
        if not self.name:
            raise ValueError("El nombre del agente no puede estar vacío")
    
    def activate(self) -> None:
        """Activa el agente cambiando su estado a RUNNING."""
        if self.status == AgentStatus.ERROR:
            raise ValueError("No se puede activar un agente en estado de error")
        self.status = AgentStatus.RUNNING
    
    def pause(self) -> None:
        """Pausa el agente."""
        if self.status == AgentStatus.RUNNING:
            self.status = AgentStatus.PAUSED
    
    def complete(self) -> None:
        """Marca el agente como completado."""
        self.status = AgentStatus.COMPLETED
    
    def set_error(self) -> None:
        """Marca el agente en estado de error."""
        self.status = AgentStatus.ERROR
    
    def reset(self) -> None:
        """Reinicia el agente al estado IDLE."""
        self.status = AgentStatus.IDLE
    
    def update_configuration(self, new_config: Dict[str, Any]) -> None:
        """
        Actualiza la configuración del agente.
        
        Args:
            new_config: Nueva configuración a aplicar
        """
        self.configuration.update(new_config)
    
    def is_active(self) -> bool:
        """
        Verifica si el agente está activo.
        
        Returns:
            bool: True si está en estado RUNNING, False en caso contrario
        """
        return self.status == AgentStatus.RUNNING

