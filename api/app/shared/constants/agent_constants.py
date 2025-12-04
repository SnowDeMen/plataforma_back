"""
Constantes relacionadas con agentes de AutoGen.
"""
from enum import Enum


class AgentType(str, Enum):
    """Tipos de agentes disponibles."""
    ASSISTANT = "assistant"
    USER_PROXY = "user_proxy"
    GROUP_CHAT = "group_chat"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Estados posibles de un agente."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class ConversationStatus(str, Enum):
    """Estados de una conversación."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


# Configuraciones por defecto de agentes
DEFAULT_AGENT_CONFIG = {
    "temperature": 0.7,
    "max_tokens": 2000,
    "timeout": 300,  # 5 minutos
}

