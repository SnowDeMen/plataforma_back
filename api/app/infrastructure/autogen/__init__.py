"""
Modulo de integracion con AutoGen Core.
Proporciona las clases base para crear agentes usando autogen-core.
"""
from .base_agent import BaseAgent, TextMessage, AgentResponse
from .agent_runtime import AgentRuntime, get_runtime
from .chat_agent import ChatAgent, ChatMessage
from .chat_manager import ChatManager

__all__ = [
    "BaseAgent",
    "TextMessage",
    "AgentResponse",
    "AgentRuntime",
    "get_runtime",
    "ChatAgent",
    "ChatMessage",
    "ChatManager"
]

