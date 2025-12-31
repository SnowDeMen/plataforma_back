"""
Modelos de base de datos (ORM).
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Date, Text, Enum as SQLEnum, JSON, Boolean
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


class AthleteModel(Base):
    """
    Modelo de base de datos para atletas.
    
    Almacena informacion completa del atleta incluyendo datos
    personales, medicos, deportivos y de performance.
    
    Estados posibles:
    - Por generar: Pendiente de generar plan
    - Por revisar: Plan en espera de validacion
    - Plan activo: Atleta con plan activo
    """
    
    __tablename__ = "athletes"
    
    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    age = Column(Integer, nullable=True)
    discipline = Column(String(100), nullable=True)
    level = Column(String(100), nullable=True)
    goal = Column(String(255), nullable=True)
    status = Column(String(50), default="Por generar", index=True)
    experience = Column(String(255), nullable=True)
    
    # Datos estructurados en JSON
    personal = Column(JSON, nullable=True)    # genero, bmi, sesionesSemanales, etc.
    medica = Column(JSON, nullable=True)      # enfermedades, horasSueno, etc.
    deportiva = Column(JSON, nullable=True)   # eventoObjetivo, records, etc.
    performance = Column(JSON, nullable=True) # historial de workouts
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Athlete(id={self.id}, name={self.name}, status={self.status})>"


class TrainingPlanModel(Base):
    """
    Modelo de base de datos para planes de entrenamiento de 4 semanas.
    
    Almacena planes generados asincronamente para atletas.
    El plan se genera como texto estructurado y puede aplicarse
    posteriormente a TrainingPeaks.
    
    Estados posibles:
    - pending: Pendiente de generar
    - generating: En proceso de generacion
    - review: Esperando aprobacion del coach
    - active: Plan aprobado y activo
    - applied: Aplicado a TrainingPeaks
    - rejected: Rechazado por el coach
    """
    
    __tablename__ = "training_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(String(255), nullable=False, index=True)
    athlete_name = Column(String(255), nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    
    # Contexto usado para generar el plan
    athlete_context = Column(JSON, nullable=True)
    generation_prompt = Column(Text, nullable=True)
    
    # Plan generado (4 semanas de workouts)
    plan_data = Column(JSON, nullable=True)
    plan_summary = Column(Text, nullable=True)
    
    # Configuracion del plan
    weeks = Column(Integer, default=4)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    # Progreso de generacion (para WebSocket)
    generation_progress = Column(Integer, default=0)
    generation_message = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<TrainingPlan(id={self.id}, athlete={self.athlete_name}, status={self.status})>"

