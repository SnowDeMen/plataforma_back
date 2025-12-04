"""
Clase base para crear agentes usando AutoGen Core.
Implementa el patron de actor para agentes con comunicacion asincrona.
"""
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from autogen_core import (
    MessageContext,
    RoutedAgent,
    message_handler,
)

from app.core.config import settings


@dataclass
class TextMessage:
    """Mensaje de texto simple para comunicacion entre agentes."""
    content: str
    source: str = "user"


@dataclass
class AgentResponse:
    """Respuesta de un agente."""
    content: str
    agent_name: str
    metadata: Optional[Dict[str, Any]] = None


class BaseAgent(RoutedAgent):
    """
    Clase base para todos los agentes del sistema.
    Extiende RoutedAgent de autogen-core para proporcionar
    funcionalidad comun y configuracion por defecto.
    
    Para crear un agente personalizado:
    1. Hereda de esta clase
    2. Implementa el metodo handle_message
    3. Opcionalmente, sobrescribe setup() para inicializacion personalizada
    
    Ejemplo:
        class MiAgente(BaseAgent):
            def __init__(self):
                super().__init__(
                    name="mi_agente",
                    system_message="Eres un asistente util."
                )
            
            async def handle_message(self, message: TextMessage, ctx: MessageContext) -> AgentResponse:
                # Procesar el mensaje y generar respuesta
                return AgentResponse(
                    content="Respuesta del agente",
                    agent_name=self.name
                )
    """
    
    def __init__(
        self,
        name: str,
        system_message: str = "Eres un asistente util.",
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Inicializa el agente base.
        
        Args:
            name: Nombre unico del agente
            system_message: Instrucciones del sistema para el agente
            model: Modelo de LLM a usar (por defecto usa settings.AUTOGEN_MODEL)
            temperature: Temperatura para generacion (por defecto usa settings)
            max_tokens: Tokens maximos de respuesta (por defecto usa settings)
            **kwargs: Argumentos adicionales para RoutedAgent
        """
        super().__init__(description=system_message, **kwargs)
        
        self.name = name
        self.system_message = system_message
        self.model = model or settings.AUTOGEN_MODEL
        self.temperature = temperature or settings.AUTOGEN_TEMPERATURE
        self.max_tokens = max_tokens or settings.AUTOGEN_MAX_TOKENS
        self._is_initialized = False
    
    async def setup(self) -> None:
        """
        Metodo de inicializacion que se llama cuando el agente se registra.
        Sobrescribir este metodo para inicializacion personalizada.
        """
        self._is_initialized = True
    
    @message_handler
    async def on_text_message(self, message: TextMessage, ctx: MessageContext) -> AgentResponse:
        """
        Manejador de mensajes de texto.
        Delega al metodo abstracto handle_message.
        
        Args:
            message: Mensaje de texto recibido
            ctx: Contexto del mensaje
            
        Returns:
            AgentResponse: Respuesta del agente
        """
        return await self.handle_message(message, ctx)
    
    @abstractmethod
    async def handle_message(self, message: TextMessage, ctx: MessageContext) -> AgentResponse:
        """
        Procesa un mensaje y genera una respuesta.
        Este metodo debe ser implementado por las clases hijas.
        
        Args:
            message: Mensaje de texto a procesar
            ctx: Contexto del mensaje con informacion adicional
            
        Returns:
            AgentResponse: Respuesta generada por el agente
        """
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """
        Obtiene la configuracion actual del agente.
        
        Returns:
            Dict con la configuracion del agente
        """
        return {
            "name": self.name,
            "system_message": self.system_message,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "is_initialized": self._is_initialized,
        }
    
    def __repr__(self) -> str:
        """Representacion en string del agente."""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"model='{self.model}', "
            f"initialized={self._is_initialized})"
        )



