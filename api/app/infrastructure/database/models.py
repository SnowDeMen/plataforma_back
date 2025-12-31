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



class AthleteModel(Base):
    """
    Modelo mapeado a la tabla sincronizada desde Airtable.
    Schema: airtable
    Table: athletes
    """
    __tablename__ = "athletes"
    __table_args__ = {"schema": "airtable"}

    airtable_record_id = Column(String, primary_key=True)
    airtable_last_modified = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)

    full_name = Column(String)
    last_name = Column(String)
    consent = Column(String)
    date_of_birth = Column(String) 
    gender = Column(String)
    country = Column(String)
    state = Column(String)
    city = Column(String)
    instagram = Column(String)
    emergency_contact_name = Column(String)
    emergency_contact_phone = Column(String)
    current_weight = Column(String)
    target_weight = Column(String)
    max_historical_weight = Column(String)
    height = Column(String)
    diseases_conditions = Column(String)
    acute_injury_disease = Column(String)
    acute_injury_type = Column(String)
    has_fractures_sprains_history = Column(String)
    fracture_history = Column(String)
    medications = Column(String)
    supplements = Column(String)
    smoker = Column(String)
    alcohol_consumption = Column(String)
    daily_sleep_hours = Column(String)
    sleep_quality = Column(String)
    meals_per_day = Column(String)
    diet_type = Column(String)
    diet_description = Column(String)
    athlete_type = Column(String)
    disciplines_count = Column(String)
    previous_sports = Column(String)
    running_experience_time = Column(String)
    cycling_experience_time = Column(String)
    swimming_experience_time = Column(String)
    short_term_goal = Column(String)
    medium_term_goal = Column(String)
    long_term_goal = Column(String)
    best_time_5k = Column(String)
    best_time_10k = Column(String)
    best_time_21k = Column(String)
    marathon_time = Column(String)
    triathlon_distance = Column(String)
    triathlon_time = Column(String)
    triathlon_place = Column(String)
    longest_run_distance = Column(String)
    longest_run_event = Column(String)
    longest_run_date = Column(String)
    training_frequency_weekly = Column(String)
    training_hours_weekly = Column(String)
    preferred_schedule = Column(String)
    schedule = Column(String)
    preferred_rest_day = Column(String)
    sacrifice_rest_day = Column(String)
    main_event = Column(String)
    event_type = Column(String)
    time_to_event = Column(String)
    secondary_events = Column(String)
    watch_brand_model = Column(String)
    has_watch = Column(String)
    watch_brand = Column(String)
    sensors_owned = Column(String)
    has_pool_access = Column(String)
    has_smart_trainer = Column(String)
    reason_for_sport = Column(String)
    annual_goals = Column(String)
    preferred_communication_channels = Column(String)
    whatsapp_group_interest = Column(String)
    discount = Column(String)
    client_status = Column(String)
    old_registration_date = Column(String)
    pending_payment = Column(String)
    form_link = Column(String)
    weight_objective_category = Column(String)
    bad_habits_percentage = Column(String)
    registration_date = Column(DateTime(timezone=True))
    training_start_date = Column(String)
    status = Column(String)

    def __repr__(self):
        return f"<Athlete(id={self.airtable_record_id}, name={self.full_name})>"


class SyncStateModel(Base):
    """
    Modelo para el estado de sincronización (cursor incremental).
    Tabla: sync_state (public schema)
    """
    __tablename__ = "sync_state"

    source = Column(String, primary_key=True)
    source_table = Column(String, primary_key=True)
    target_schema = Column(String, primary_key=True)
    target_table = Column(String, primary_key=True)

    cursor_last_modified = Column(DateTime(timezone=True), nullable=False, default=datetime(1970, 1, 1, tzinfo=None)) # Default handled by DB usually, but safe to set
    
    last_run_started_at = Column(DateTime(timezone=True), nullable=True)
    last_run_completed_at = Column(DateTime(timezone=True), nullable=True)
    last_run_status = Column(String, nullable=True) # running | success | error
    last_run_error = Column(String, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SyncState({self.source_table} -> {self.target_table}, status={self.last_run_status})>"

