"""
Agente simple de ejemplo usando AutoGen Core.
Demuestra como crear un agente basico que responde mensajes.
"""
from typing import Optional, Dict, Any

from autogen_core import MessageContext
from autogen_ext.models.openai import OpenAIChatCompletionClient

from app.core.config import settings
from .base_agent import BaseAgent, TextMessage, AgentResponse


class SimpleAgent(BaseAgent):
    """
    Agente simple que usa OpenAI para generar respuestas.
    
    Ejemplo de uso:
        async with AgentRuntime() as runtime:
            agent_id = await runtime.register_agent(
                SimpleAgent,
                "asistente",
                system_message="Eres un asistente experto en Python."
            )
            
            response = await runtime.send_message(
                agent_id,
                TextMessage(content="Hola, como puedo crear una lista en Python?")
            )
            print(response.content)
    """
    
    def __init__(
        self,
        name: str,
        system_message: str = "Eres un asistente util y amigable.",
        model: Optional[str] = None,
        **kwargs
    ):
        """
        Inicializa el agente simple.
        
        Args:
            name: Nombre del agente
            system_message: Instrucciones del sistema
            model: Modelo de OpenAI a usar
            **kwargs: Argumentos adicionales
        """
        super().__init__(
            name=name,
            system_message=system_message,
            model=model,
            **kwargs
        )
        self._client: Optional[OpenAIChatCompletionClient] = None
        self._conversation_history = []
    
    async def setup(self) -> None:
        """Inicializa el cliente de OpenAI."""
        await super().setup()
        
        self._client = OpenAIChatCompletionClient(
            model=self.model,
            api_key=settings.OPENAI_API_KEY,
        )
    
    async def handle_message(self, message: TextMessage, ctx: MessageContext) -> AgentResponse:
        """
        Procesa un mensaje y genera una respuesta usando OpenAI.
        
        Args:
            message: Mensaje de texto a procesar
            ctx: Contexto del mensaje
            
        Returns:
            AgentResponse: Respuesta generada
        """
        if not self._client:
            await self.setup()
        
        # Agregar mensaje del usuario al historial
        self._conversation_history.append({
            "role": "user",
            "content": message.content
        })
        
        # Preparar mensajes para la API
        messages = [
            {"role": "system", "content": self.system_message}
        ] + self._conversation_history
        
        # Llamar a la API de OpenAI
        response = await self._client.create(messages=messages)
        
        # Extraer contenido de la respuesta
        response_content = response.content if hasattr(response, 'content') else str(response)
        
        # Agregar respuesta al historial
        self._conversation_history.append({
            "role": "assistant",
            "content": response_content
        })
        
        return AgentResponse(
            content=response_content,
            agent_name=self.name,
            metadata={
                "model": self.model,
                "history_length": len(self._conversation_history)
            }
        )
    
    def reset_conversation(self) -> None:
        """Limpia el historial de conversacion."""
        self._conversation_history = []
    
    def get_conversation_history(self) -> list:
        """Obtiene el historial de conversacion."""
        return self._conversation_history.copy()



