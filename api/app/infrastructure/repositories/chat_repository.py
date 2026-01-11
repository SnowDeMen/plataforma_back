"""
Repositorio para operaciones de persistencia de ChatSession.
Maneja el almacenamiento y recuperacion del historial de chat en base de datos.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from app.infrastructure.database.models import ChatSessionModel


class ChatRepository:
    """
    Repositorio para operaciones CRUD de ChatSession.
    
    Proporciona metodos para:
    - Crear sesiones de chat
    - Actualizar historial de mensajes
    - Recuperar sesiones para restaurar conversaciones
    """
    
    def __init__(self, db: AsyncSession):
        """
        Inicializa el repositorio con una sesion de base de datos.
        
        Args:
            db: Sesion asincrona de SQLAlchemy
        """
        self.db = db
    
    async def create(
        self,
        session_id: str,
        athlete_name: str,
        athlete_id: Optional[str] = None,
        system_message: Optional[str] = None,
        agent_config: Optional[Dict[str, Any]] = None
    ) -> ChatSessionModel:
        """
        Crea una nueva sesion de chat en la base de datos.
        
        Args:
            session_id: ID unico de la sesion de entrenamiento
            athlete_name: Nombre del atleta asociado
            athlete_id: ID del atleta asociado (opcional, para busqueda robusta)
            system_message: Mensaje de sistema del agente
            agent_config: Configuracion adicional del agente
            
        Returns:
            ChatSessionModel: Modelo creado
        """
        chat_session = ChatSessionModel(
            session_id=session_id,
            athlete_name=athlete_name,
            athlete_id=athlete_id,
            messages=[],
            system_message=system_message,
            agent_config=agent_config or {},
            is_active=True
        )
        
        self.db.add(chat_session)
        await self.db.flush()
        await self.db.refresh(chat_session)
        
        logger.info(f"ChatSession creada: {session_id} para atleta {athlete_name}")
        
        return chat_session
    
    async def get_by_session_id(self, session_id: str) -> Optional[ChatSessionModel]:
        """
        Obtiene una sesion de chat por su session_id.
        
        Args:
            session_id: ID de la sesion a buscar
            
        Returns:
            ChatSessionModel o None si no existe
        """
        query = select(ChatSessionModel).where(
            ChatSessionModel.session_id == session_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_athlete(
        self, 
        athlete_name: str, 
        athlete_id: Optional[str] = None,
        active_only: bool = True
    ) -> List[ChatSessionModel]:
        """
        Obtiene todas las sesiones de chat de un atleta.
        Si se proporciona athlete_id, busca por ID O por nombre parcial (para compatibilidad).
        
        Args:
            athlete_name: Nombre del atleta
            athlete_id: ID del atleta (opcional)
            active_only: Si solo retornar sesiones activas
            
        Returns:
            Lista de ChatSessionModel
        """
        if athlete_id:
            # Search by ID OR partial name match to include old sessions without ID
            # and new sessions with ID.
            query = select(ChatSessionModel).where(
                (ChatSessionModel.athlete_id == athlete_id) | 
                (ChatSessionModel.athlete_name.ilike(f"%{athlete_name}%"))
            )
        else:
            # Fallback to name only
            query = select(ChatSessionModel).where(
                ChatSessionModel.athlete_name.ilike(f"%{athlete_name}%")
            )
        
        if active_only:
            query = query.where(ChatSessionModel.is_active == True)
        
        query = query.order_by(ChatSessionModel.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_messages(
        self, 
        session_id: str, 
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        Actualiza el historial de mensajes de una sesion.
        
        Args:
            session_id: ID de la sesion
            messages: Lista actualizada de mensajes
            
        Returns:
            True si se actualizo correctamente
        """
        query = (
            update(ChatSessionModel)
            .where(ChatSessionModel.session_id == session_id)
            .values(
                messages=messages,
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.debug(f"Mensajes actualizados para sesion {session_id}")
            return True
        
        return False
    
    async def add_message(
        self, 
        session_id: str, 
        message: Dict[str, Any]
    ) -> bool:
        """
        Agrega un mensaje al historial de una sesion.
        
        Primero obtiene los mensajes actuales, agrega el nuevo y actualiza.
        
        Args:
            session_id: ID de la sesion
            message: Mensaje a agregar
            
        Returns:
            True si se agrego correctamente
        """
        chat_session = await self.get_by_session_id(session_id)
        
        if not chat_session:
            logger.warning(f"Sesion no encontrada: {session_id}")
            return False
        
        # Obtener mensajes actuales y agregar el nuevo
        current_messages = chat_session.messages or []
        current_messages.append(message)
        
        return await self.update_messages(session_id, current_messages)
    
    async def deactivate(self, session_id: str) -> bool:
        """
        Marca una sesion de chat como inactiva.
        
        Args:
            session_id: ID de la sesion a desactivar
            
        Returns:
            True si se desactivo correctamente
        """
        query = (
            update(ChatSessionModel)
            .where(ChatSessionModel.session_id == session_id)
            .values(
                is_active=False,
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db.execute(query)
        
        if result.rowcount > 0:
            logger.info(f"ChatSession desactivada: {session_id}")
            return True
        
        return False
    
    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de mensajes de una sesion.
        
        Args:
            session_id: ID de la sesion
            
        Returns:
            Lista de mensajes o lista vacia si no existe
        """
        chat_session = await self.get_by_session_id(session_id)
        
        if chat_session:
            return chat_session.messages or []
        
        return []
    
    async def update_system_message(
        self, 
        session_id: str, 
        system_message: str
    ) -> bool:
        """
        Actualiza el mensaje de sistema de una sesion.
        
        Args:
            session_id: ID de la sesion
            system_message: Nuevo mensaje de sistema
            
        Returns:
            True si se actualizo correctamente
        """
        query = (
            update(ChatSessionModel)
            .where(ChatSessionModel.session_id == session_id)
            .values(
                system_message=system_message,
                updated_at=datetime.utcnow()
            )
        )
        
        result = await self.db.execute(query)
        return result.rowcount > 0

    async def delete(self, session_id: str) -> bool:
        """
        Elimina permanentemente una sesion de chat de la base de datos.
        
        Args:
            session_id: ID de la sesion a eliminar
            
        Returns:
            True si se elimino correctamente
        """
        chat_session = await self.get_by_session_id(session_id)
        
        if not chat_session:
            logger.warning(f"Sesion no encontrada para eliminar: {session_id}")
            return False
        
        await self.db.delete(chat_session)
        logger.info(f"ChatSession eliminada permanentemente: {session_id}")
        return True


