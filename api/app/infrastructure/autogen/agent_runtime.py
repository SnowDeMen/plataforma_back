"""
Runtime para gestionar la ejecucion de agentes con AutoGen Core.
Proporciona un entorno de ejecucion centralizado para los agentes.
"""
from typing import Dict, Optional, Type, Any

from autogen_core import SingleThreadedAgentRuntime, AgentId

from .base_agent import BaseAgent


class AgentRuntime:
    """
    Gestor del runtime de agentes.
    Centraliza la creacion, registro y comunicacion entre agentes.
    
    Uso:
        runtime = AgentRuntime()
        await runtime.start()
        
        # Registrar un agente
        agent_id = await runtime.register_agent(MiAgente, "mi_agente")
        
        # Enviar mensaje
        response = await runtime.send_message(agent_id, "Hola")
        
        await runtime.stop()
    """
    
    def __init__(self):
        """Inicializa el runtime de agentes."""
        self._runtime: Optional[SingleThreadedAgentRuntime] = None
        self._registered_agents: Dict[str, AgentId] = {}
        self._is_running = False
    
    async def start(self) -> None:
        """
        Inicia el runtime de agentes.
        Debe llamarse antes de registrar o usar agentes.
        """
        if self._is_running:
            return
        
        self._runtime = SingleThreadedAgentRuntime()
        self._is_running = True
    
    async def stop(self) -> None:
        """
        Detiene el runtime de agentes.
        Limpia todos los agentes registrados.
        """
        if not self._is_running:
            return
        
        if self._runtime:
            await self._runtime.stop()
        
        self._registered_agents.clear()
        self._is_running = False
    
    async def register_agent(
        self,
        agent_class: Type[BaseAgent],
        agent_name: str,
        **kwargs
    ) -> AgentId:
        """
        Registra un nuevo agente en el runtime.
        
        Args:
            agent_class: Clase del agente a registrar
            agent_name: Nombre unico para el agente
            **kwargs: Argumentos adicionales para el constructor del agente
            
        Returns:
            AgentId: Identificador del agente registrado
            
        Raises:
            RuntimeError: Si el runtime no esta iniciado
            ValueError: Si ya existe un agente con ese nombre
        """
        if not self._is_running or not self._runtime:
            raise RuntimeError("El runtime no esta iniciado. Llama a start() primero.")
        
        if agent_name in self._registered_agents:
            raise ValueError(f"Ya existe un agente registrado con el nombre '{agent_name}'")
        
        # Registrar el tipo de agente
        agent_type = await self._runtime.register(
            agent_name,
            lambda: agent_class(name=agent_name, **kwargs),
        )
        
        # Crear el AgentId
        agent_id = AgentId(type=agent_name, key="default")
        self._registered_agents[agent_name] = agent_id
        
        return agent_id
    
    async def send_message(
        self,
        agent_id: AgentId,
        message: Any,
        sender: Optional[str] = None
    ) -> Any:
        """
        Envia un mensaje a un agente.
        
        Args:
            agent_id: ID del agente destinatario
            message: Mensaje a enviar
            sender: Nombre del remitente (opcional)
            
        Returns:
            Respuesta del agente
            
        Raises:
            RuntimeError: Si el runtime no esta iniciado
        """
        if not self._is_running or not self._runtime:
            raise RuntimeError("El runtime no esta iniciado. Llama a start() primero.")
        
        return await self._runtime.send_message(message, agent_id)
    
    def get_agent_id(self, agent_name: str) -> Optional[AgentId]:
        """
        Obtiene el ID de un agente por su nombre.
        
        Args:
            agent_name: Nombre del agente
            
        Returns:
            AgentId o None si no existe
        """
        return self._registered_agents.get(agent_name)
    
    def list_agents(self) -> Dict[str, AgentId]:
        """
        Lista todos los agentes registrados.
        
        Returns:
            Dict con nombre -> AgentId
        """
        return self._registered_agents.copy()
    
    @property
    def is_running(self) -> bool:
        """Indica si el runtime esta en ejecucion."""
        return self._is_running
    
    async def __aenter__(self) -> "AgentRuntime":
        """Permite usar el runtime como context manager."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Detiene el runtime al salir del contexto."""
        await self.stop()


# Instancia global del runtime
_runtime: Optional[AgentRuntime] = None


def get_runtime() -> AgentRuntime:
    """
    Obtiene la instancia global del runtime.
    Crea una nueva si no existe.
    
    Returns:
        AgentRuntime: Instancia del runtime
    """
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime


async def reset_runtime() -> None:
    """
    Resetea el runtime global.
    Util para testing o reinicializacion.
    """
    global _runtime
    if _runtime and _runtime.is_running:
        await _runtime.stop()
    _runtime = None



