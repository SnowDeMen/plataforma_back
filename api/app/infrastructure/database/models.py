"""
Modelos de base de datos (ORM).
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, Enum as SQLEnum, JSON, Boolean
from sqlalchemy.sql import func

from app.infrastructure.database.session import Base
from app.shared.constants.agent_constants import AgentType, AgentStatus, ConversationStatus


class AgentModel(Base):
    """Modelo de base de datos para agentes."""
    
    __tablename__ = "agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(SQLEnum(AgentType), nullable=False)
    status = Column(SQLEnum(AgentStatus), default=AgentStatus.IDLE)
    configuration = Column(JSON, nullable=True)
    system_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, type={self.type})>"


class ChatSessionModel(Base):
    """
    Modelo de base de datos para sesiones de chat.
    Almacena el historial de conversaciones ligado a una sesion de entrenamiento.
    """
    
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    athlete_name = Column(String(255), nullable=False, index=True)
    messages = Column(JSON, nullable=False, default=list)
    system_message = Column(Text, nullable=True)
    agent_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, session_id={self.session_id}, athlete={self.athlete_name})>"


class ConversationModel(Base):
    """Modelo de base de datos para conversaciones."""
    
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    status = Column(SQLEnum(ConversationStatus), default=ConversationStatus.ACTIVE)
    agent_ids = Column(JSON, nullable=False)  # Lista de IDs de agentes participantes
    messages = Column(JSON, nullable=True)  # Historial de mensajes
    conversation_meta = Column("metadata", JSON, nullable=True)  # Metadatos adicionales de la conversacion
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, title={self.title}, status={self.status})>"


class TrainingModel(Base):
    """Modelo de base de datos para entrenamientos."""
    
    __tablename__ = "trainings"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    conversation_id = Column(Integer, nullable=True)
    configuration = Column(JSON, nullable=False)
    results = Column(JSON, nullable=True)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Training(id={self.id}, name={self.name}, status={self.status})>"

