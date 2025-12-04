"""
ChatManager - Gestor centralizado de agentes de chat por sesion.
Maneja el ciclo de vida de los ChatAgents y su vinculacion con sesiones.
"""
from typing import Optional, Dict, List, Any
from datetime import datetime

from loguru import logger

from .chat_agent import ChatAgent


class ChatManager:
    """
    Gestor centralizado de agentes de chat.
    
    Responsabilidades:
    - Crear y mantener agentes de chat por sesion
    - Proporcionar acceso a agentes existentes
    - Gestionar el ciclo de vida de los agentes
    
    Uso:
        # Crear un agente para una sesion
        agent = ChatManager.create_agent(
            session_id="uuid-123",
            athlete_name="Luis Aragon",
            system_message="Eres un asistente de entrenamiento."
        )
        
        # Obtener agente existente
        agent = ChatManager.get_agent("uuid-123")
        
        # Procesar mensaje
        response = await agent.process_message("Hola")
    """
    
    # Almacenamiento de agentes activos en memoria
    _agents: Dict[str, ChatAgent] = {}
    
    # Configuracion por defecto para nuevos agentes
    DEFAULT_AGENT_CONFIG = {
        "name_prefix": "coach_",
        "system_message": None  # Usara el DEFAULT_SYSTEM_MESSAGE del ChatAgent
    }
    
    @classmethod
    def create_agent(
        cls,
        session_id: str,
        athlete_name: str,
        athlete_info: Optional[Dict[str, Any]] = None,
        system_message: Optional[str] = None,
        initial_history: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None
    ) -> ChatAgent:
        """
        Crea un nuevo agente de chat para una sesion.
        
        Si ya existe un agente para la sesion, lo retorna.
        
        Args:
            session_id: ID de la sesion de entrenamiento
            athlete_name: Nombre del atleta asociado
            athlete_info: Informacion adicional del atleta para contexto
            system_message: Mensaje de sistema personalizado (opcional)
            initial_history: Historial previo para restaurar (opcional)
            model: Modelo de LLM a usar (opcional)
            
        Returns:
            ChatAgent: Agente creado o existente
        """
        # Si ya existe un agente para esta sesion, retornarlo
        if session_id in cls._agents:
            logger.debug(f"Retornando agente existente para sesion {session_id}")
            return cls._agents[session_id]
        
        # Construir nombre del agente
        agent_name = f"{cls.DEFAULT_AGENT_CONFIG['name_prefix']}{session_id[:8]}"
        
        # Usar system message por defecto si no se proporciona
        final_system_message = system_message or cls._build_default_system_message(
            athlete_name
        )
        
        # Crear el agente con contexto del atleta
        agent = ChatAgent(
            name=agent_name,
            session_id=session_id,
            athlete_name=athlete_name,
            athlete_info=athlete_info,
            system_message=final_system_message,
            model=model,
            initial_history=initial_history
        )
        
        # Almacenar en memoria
        cls._agents[session_id] = agent
        
        logger.info(
            f"ChatManager: Agente creado para sesion {session_id}, "
            f"atleta: {athlete_name}"
        )
        
        return agent
    
    @classmethod
    def _build_default_system_message(cls, athlete_name: str) -> Optional[str]:
        """
        Construye el mensaje de sistema personalizado para el atleta.
        
        Si no hay system_message en la config, retorna None y el ChatAgent
        usara su DEFAULT_SYSTEM_MESSAGE.
        """
        base_message = cls.DEFAULT_AGENT_CONFIG.get("system_message")
        
        if not base_message:
            # Retornar None para usar el DEFAULT_SYSTEM_MESSAGE del ChatAgent
            # que ya incluye toda la logica de generacion de entrenamientos ZWO
            return None
        
        return f"{base_message}\n\nEstas trabajando con el atleta: {athlete_name}."
    
    @classmethod
    def get_agent(cls, session_id: str) -> Optional[ChatAgent]:
        """
        Obtiene un agente de chat por ID de sesion.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            ChatAgent o None si no existe
        """
        return cls._agents.get(session_id)
    
    @classmethod
    def has_agent(cls, session_id: str) -> bool:
        """
        Verifica si existe un agente para una sesion.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            True si existe el agente
        """
        return session_id in cls._agents
    
    @classmethod
    def remove_agent(cls, session_id: str) -> bool:
        """
        Elimina un agente de chat.
        
        Args:
            session_id: ID de la sesion del agente a eliminar
            
        Returns:
            True si se elimino, False si no existia
        """
        if session_id in cls._agents:
            del cls._agents[session_id]
            logger.info(f"ChatManager: Agente eliminado para sesion {session_id}")
            return True
        return False
    
    @classmethod
    def get_all_sessions(cls) -> List[str]:
        """
        Obtiene todos los IDs de sesion con agentes activos.
        
        Returns:
            Lista de session_ids
        """
        return list(cls._agents.keys())
    
    @classmethod
    def get_agent_count(cls) -> int:
        """Retorna el numero de agentes activos."""
        return len(cls._agents)
    
    @classmethod
    def restore_agent(
        cls,
        session_id: str,
        athlete_name: str,
        history: List[Dict[str, Any]],
        system_message: Optional[str] = None
    ) -> ChatAgent:
        """
        Restaura un agente con su historial desde la base de datos.
        
        Util para retomar conversaciones previas.
        
        Args:
            session_id: ID de la sesion
            athlete_name: Nombre del atleta
            history: Historial de mensajes previos
            system_message: Mensaje de sistema (opcional)
            
        Returns:
            ChatAgent restaurado
        """
        # Si ya existe, actualizamos su historial
        if session_id in cls._agents:
            agent = cls._agents[session_id]
            agent.load_history(history)
            logger.info(f"ChatManager: Historial actualizado para sesion {session_id}")
            return agent
        
        # Crear nuevo agente con el historial
        return cls.create_agent(
            session_id=session_id,
            athlete_name=athlete_name,
            system_message=system_message,
            initial_history=history
        )
    
    @classmethod
    def clear_all(cls) -> int:
        """
        Elimina todos los agentes activos.
        Util para limpieza al cerrar la aplicacion.
        
        Returns:
            Numero de agentes eliminados
        """
        count = len(cls._agents)
        cls._agents.clear()
        logger.info(f"ChatManager: Eliminados {count} agentes")
        return count


