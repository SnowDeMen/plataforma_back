"""
Casos de uso relacionados con operaciones de chat.
Contiene la logica de negocio para interactuar con el agente de chat.
"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.application.dto.chat_dto import (
    ChatRequestDTO,
    ChatResponseDTO,
    ChatHistoryDTO,
    ChatMessageDTO,
    ChatSessionInfoDTO,
    ChatConfigUpdateDTO
)
from app.infrastructure.repositories.chat_repository import ChatRepository
from app.infrastructure.autogen.chat_manager import ChatManager
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.mcp.mcp_server_manager import MCPServerManager
from app.shared.exceptions.domain import SessionNotFoundException
from app.shared.utils.audit_logger import AuditLogger


class ChatUseCases:
    """
    Casos de uso para operaciones de chat.
    
    Maneja la interaccion entre el usuario y el agente de chat,
    incluyendo persistencia del historial en base de datos.
    """
    
    def __init__(self, db: AsyncSession):
        """
        Inicializa los casos de uso con una sesion de base de datos.
        
        Args:
            db: Sesion asincrona de SQLAlchemy
        """
        self.db = db
        self.repository = ChatRepository(db)
    
    async def ensure_session_logger(self, session_id: str) -> bool:
        """
        Asegura que el session_logger de auditoria existe para la sesion.
        
        Este metodo debe llamarse ANTES de log_request para garantizar
        que los logs de request se registren correctamente, especialmente
        en sesiones reanudadas donde el logger no existe en memoria.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            True si el logger existe o fue creado, False si la sesion no existe
        """
        chat_session = await self.repository.get_by_session_id(session_id)
        
        if not chat_session:
            return False
        
        # Crear o recuperar el logger de sesion
        AuditLogger.get_session_logger(
            session_id=session_id,
            athlete_name=chat_session.athlete_name,
            resume=True
        )
        
        return True
    
    async def _ensure_mcp_initialized(self, session_id: str) -> bool:
        """
        Verifica e inicializa el servidor MCP si hay un driver activo pero no esta conectado.
        
        Esto es necesario para sesiones restauradas donde el agente existe en memoria
        pero el servidor MCP no fue reinicializado despues de un reinicio del servidor.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            True si el servidor MCP esta listo, False si no hay driver disponible
        """
        # Verificar si el servidor MCP ya esta inicializado para esta sesion
        if MCPServerManager.is_running() and MCPServerManager.get_current_session_id() == session_id:
            return True
        
        # Buscar si hay un driver activo para esta sesion
        driver_session = DriverManager.get_session(session_id)
        
        if not driver_session or not driver_session.is_active:
            # No hay driver activo, el servidor MCP no puede inicializarse
            logger.debug(f"No hay driver activo para sesion {session_id}, servidor MCP no disponible")
            return False
        
        # Hay driver activo, iniciar servidor MCP
        mcp_initialized = MCPServerManager.start(
            driver=driver_session.driver,
            wait=driver_session.wait,
            session_id=session_id,
            run_server=False
        )
        
        if mcp_initialized:
            logger.info(f"Servidor MCP reinicializado para sesion restaurada {session_id}")
            AuditLogger.log_mcp_call(
                session_id=session_id,
                action="MCP_SERVER_REINITIALIZE",
                details={
                    "reason": "session_restored",
                    "tools_available": MCPServerManager.get_available_tools()
                },
                success=True
            )
        else:
            logger.warning(f"No se pudo reinicializar servidor MCP para sesion {session_id}")
        
        return mcp_initialized
    
    async def send_message(
        self, 
        session_id: str, 
        dto: ChatRequestDTO
    ) -> ChatResponseDTO:
        """
        Envia un mensaje al chat y obtiene la respuesta del agente.
        
        Flujo:
        1. Verifica que exista la sesion de chat
        2. Obtiene o restaura el agente del ChatManager
        3. Procesa el mensaje con el agente
        4. Persiste el historial actualizado en base de datos
        5. Retorna la respuesta
        
        Args:
            session_id: ID de la sesion de entrenamiento
            dto: Datos del mensaje a enviar
            
        Returns:
            ChatResponseDTO: Respuesta del agente
            
        Raises:
            SessionNotFoundException: Si la sesion no existe
        """
        # Verificar que existe la sesion de chat
        chat_session = await self.repository.get_by_session_id(session_id)
        
        if not chat_session:
            logger.warning(f"Sesion de chat no encontrada: {session_id}")
            raise SessionNotFoundException(session_id)
        
        # Asegurar que el logger de auditoria existe (para sesiones restauradas)
        AuditLogger.get_session_logger(
            session_id=session_id,
            athlete_name=chat_session.athlete_name,
            resume=True
        )
        
        # Verificar e inicializar MCP si hay driver activo pero MCP no conectado
        await self._ensure_mcp_initialized(session_id)
        
        # Obtener o restaurar el agente
        agent = ChatManager.get_agent(session_id)
        
        if not agent:
            # Restaurar agente con historial desde BD
            agent = ChatManager.restore_agent(
                session_id=session_id,
                athlete_name=chat_session.athlete_name,
                history=chat_session.messages or [],
                system_message=chat_session.system_message
            )
        
        # Log del mensaje del usuario
        AuditLogger.log_chat(
            session_id=session_id,
            role="user",
            content=dto.message
        )
        
        # Procesar mensaje con el agente
        response = await agent.process_message(dto.message)
        
        # Log de la respuesta del agente
        AuditLogger.log_chat(
            session_id=session_id,
            role="assistant",
            content=response.content,
            metadata=response.metadata
        )
        
        # Persistir historial actualizado
        updated_history = agent.get_history()
        await self.repository.update_messages(session_id, updated_history)
        
        logger.info(
            f"Mensaje procesado para sesion {session_id}. "
            f"Historial: {len(updated_history)} mensajes"
        )
        
        return ChatResponseDTO(
            session_id=session_id,
            message=response.content,
            agent_name=response.agent_name,
            timestamp=datetime.utcnow().isoformat(),
            history_length=len(updated_history),
            metadata=response.metadata
        )
    
    async def get_history(self, session_id: str) -> ChatHistoryDTO:
        """
        Obtiene el historial completo de una sesion de chat.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            ChatHistoryDTO: Historial completo
            
        Raises:
            SessionNotFoundException: Si la sesion no existe
        """
        # Asegurar que el logger de auditoria existe
        chat_session = await self.repository.get_by_session_id(session_id)
        
        if not chat_session:
            raise SessionNotFoundException(session_id)
        
        AuditLogger.get_session_logger(
            session_id=session_id,
            athlete_name=chat_session.athlete_name,
            resume=True
        )
        
        # Log del evento
        AuditLogger.log_event(
            session_id=session_id,
            event="HISTORY_RETRIEVED",
            details={"message_count": len(chat_session.messages or [])}
        )
        
        # Convertir mensajes a DTOs
        messages = [
            ChatMessageDTO(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp"),
                metadata=msg.get("metadata", {})
            )
            for msg in (chat_session.messages or [])
        ]
        
        result = ChatHistoryDTO(
            session_id=session_id,
            athlete_name=chat_session.athlete_name,
            athlete_id=chat_session.athlete_id,
            messages=messages,
            is_active=chat_session.is_active,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at
        )
        
        logger.info(f"Historial obtenido para sesion {session_id}: {len(messages)} mensajes")
        
        return result
    
    async def get_session_info(self, session_id: str) -> ChatSessionInfoDTO:
        """
        Obtiene informacion resumida de una sesion de chat.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            ChatSessionInfoDTO: Informacion resumida
            
        Raises:
            SessionNotFoundException: Si la sesion no existe
        """
        chat_session = await self.repository.get_by_session_id(session_id)
        
        if not chat_session:
            raise SessionNotFoundException(session_id)
        
        messages = chat_session.messages or []
        last_message = None
        
        if messages:
            last_msg = messages[-1]
            content = last_msg.get("content", "")
            # Truncar mensaje si es muy largo
            last_message = content[:100] + "..." if len(content) > 100 else content
        
        return ChatSessionInfoDTO(
            session_id=session_id,
            athlete_name=chat_session.athlete_name,
            athlete_id=chat_session.athlete_id,
            message_count=len(messages),
            is_active=DriverManager.is_session_active(session_id),
            last_message=last_message,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at
        )
    
    async def update_config(
        self, 
        session_id: str, 
        dto: ChatConfigUpdateDTO
    ) -> bool:
        """
        Actualiza la configuracion del chat.
        
        Args:
            session_id: ID de la sesion
            dto: Datos de configuracion a actualizar
            
        Returns:
            True si se actualizo correctamente
            
        Raises:
            SessionNotFoundException: Si la sesion no existe
        """
        # Asegurar que el logger de auditoria existe
        chat_session = await self.repository.get_by_session_id(session_id)
        
        if not chat_session:
            raise SessionNotFoundException(session_id)
        
        AuditLogger.get_session_logger(
            session_id=session_id,
            athlete_name=chat_session.athlete_name,
            resume=True
        )
        
        # Log del evento
        AuditLogger.log_event(
            session_id=session_id,
            event="CONFIG_UPDATE_STARTED",
            details={"has_system_message": bool(dto.system_message)}
        )
        
        # Actualizar system message si se proporciona
        if dto.system_message:
            await self.repository.update_system_message(
                session_id, 
                dto.system_message
            )
            
            # Actualizar agente en memoria si existe
            agent = ChatManager.get_agent(session_id)
            if agent:
                agent.update_system_message(dto.system_message)
            
            logger.info(f"System message actualizado para sesion {session_id}")
            
            # Log del evento exitoso
            AuditLogger.log_event(
                session_id=session_id,
                event="CONFIG_UPDATE_COMPLETED",
                details={"system_message_length": len(dto.system_message)}
            )
        
        return True
    
    async def clear_history(self, session_id: str) -> bool:
        """
        Limpia el historial de mensajes de una sesion.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            True si se limpio correctamente
            
        Raises:
            SessionNotFoundException: Si la sesion no existe
        """
        # Asegurar que el logger de auditoria existe
        chat_session = await self.repository.get_by_session_id(session_id)
        
        if not chat_session:
            raise SessionNotFoundException(session_id)
        
        AuditLogger.get_session_logger(
            session_id=session_id,
            athlete_name=chat_session.athlete_name,
            resume=True
        )
        
        # Log del evento
        AuditLogger.log_event(
            session_id=session_id,
            event="HISTORY_CLEAR_STARTED",
            details={"previous_message_count": len(chat_session.messages or [])}
        )
        
        # Limpiar en base de datos
        await self.repository.update_messages(session_id, [])
        
        # Limpiar en agente si existe en memoria
        agent = ChatManager.get_agent(session_id)
        if agent:
            agent.clear_history()
        
        logger.info(f"Historial limpiado para sesion {session_id}")
        
        # Log del evento completado
        AuditLogger.log_event(
            session_id=session_id,
            event="HISTORY_CLEAR_COMPLETED"
        )
        
        return True
    
    async def get_athlete_sessions(
        self, 
        athlete_name: str, 
        athlete_id: Optional[str] = None,
        active_only: bool = True
    ) -> List[ChatSessionInfoDTO]:
        """
        Obtiene todas las sesiones de chat de un atleta.
        
        Util para mostrar historial de conversaciones previas.
        
        Args:
            athlete_name: Nombre del atleta
            active_only: Si solo retornar sesiones activas
            
        Returns:
            Lista de ChatSessionInfoDTO
        """
        sessions = await self.repository.get_by_athlete(
            athlete_name=athlete_name, 
            athlete_id=athlete_id,
            active_only=active_only
        )
        
        result = []
        for session in sessions:
            messages = session.messages or []
            last_message = None
            
            if messages:
                last_msg = messages[-1]
                content = last_msg.get("content", "")
                last_message = content[:100] + "..." if len(content) > 100 else content
            
            result.append(ChatSessionInfoDTO(
                session_id=session.session_id,
                athlete_name=session.athlete_name,
                athlete_id=session.athlete_id,
                message_count=len(messages),
                is_active=DriverManager.is_session_active(session.session_id),
                last_message=last_message,
                created_at=session.created_at,
                updated_at=session.updated_at
            ))
        
        return result

    async def delete_session(self, session_id: str) -> bool:
        """
        Elimina permanentemente una sesion de chat.
        
        Elimina la sesion de la base de datos y limpia recursos asociados.
        
        Args:
            session_id: ID de la sesion a eliminar
            
        Returns:
            True si se elimino correctamente
            
        Raises:
            SessionNotFoundException: Si la sesion no existe
        """
        # Verificar que existe la sesion
        chat_session = await self.repository.get_by_session_id(session_id)
        
        if not chat_session:
            raise SessionNotFoundException(session_id)
        
        # Log del evento
        AuditLogger.log_event(
            session_id=session_id,
            event="SESSION_DELETE_REQUESTED",
            details={"athlete_name": chat_session.athlete_name}
        )
        
        # Eliminar agente de memoria si existe
        ChatManager.remove_agent(session_id)
        
        # Eliminar de la base de datos
        deleted = await self.repository.delete(session_id)
        
        if deleted:
            logger.info(f"Sesion {session_id} eliminada permanentemente")
            AuditLogger.log_event(
                session_id=session_id,
                event="SESSION_DELETED"
            )
        
        return deleted
    




