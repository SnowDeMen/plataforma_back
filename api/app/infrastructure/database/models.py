"""
Modelos de base de datos (ORM).
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Date, Text, Enum as SQLEnum, JSON, Boolean
from sqlalchemy.sql import func

from app.infrastructure.database.session import Base
from app.shared.constants.agent_constants import AgentType, AgentStatus, ConversationStatus


class SyncStateModel(Base):
    """
    Modelo para cursor de sincronización (Airtable -> Postgres).
    Define el estado de la sincronización incremental.
    """
    __tablename__ = "sync_state"
    
    source = Column(Text, primary_key=True)
    source_table = Column(Text, primary_key=True)
    target_schema = Column(Text, primary_key=True)
    target_table = Column(Text, primary_key=True)
    
    cursor_last_modified = Column(DateTime(timezone=True), nullable=False, server_default=func.text("'1970-01-01 00:00:00+00'::timestamp with time zone"))
    last_run_started_at = Column(DateTime(timezone=True), nullable=True)
    last_run_completed_at = Column(DateTime(timezone=True), nullable=True)
    last_run_status = Column(Text, nullable=True)
    last_run_error = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SyncState({self.source_table} -> {self.target_table})>"


class SystemSettingsModel(Base):
    """
    Modelo para configuraciones dinámicas del sistema.
    Permite cambiar parámetros (como intervalos de notación) sin reiniciar el server.
    """
    __tablename__ = "system_settings"
    
    key = Column(String(255), primary_key=True, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemSettings(key={self.key}, value={self.value})>"


class TelegramSubscriberModel(Base):
    """
    Modelo para suscriptores de notificaciones de Telegram.
    Guarda los chat_id de quienes han iniciado conversación con el bot.
    """
    __tablename__ = "telegram_subscribers"
    
    chat_id = Column(String(255), primary_key=True, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<TelegramSubscriber(chat_id={self.chat_id}, username={self.username})>"


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
    athlete_id = Column(String(255), nullable=True, index=True)
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
    Combina la informacion sincronizada de Airtable (perfil)
    con la informacion generada por la app (performance).
    
    Tabla: athletes (public schema)
    """
    __tablename__ = "athletes"
    
    # Identificadores y Metadata
    id = Column(String(255), primary_key=True)  # Mismo que airtable_record_id
    airtable_id = Column(String(255), nullable=True, index=True) # ID redundante o external_id
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Campos de Sincronizacion
    airtable_last_modified = Column(DateTime(timezone=True), nullable=True)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    last_training_generation_at = Column(DateTime(timezone=True), nullable=True)

    # Datos Principales (Mapeados desde Airtable)
    name = Column(String(255), nullable=False, index=True)
    full_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    tp_username = Column(String, nullable=True)  # Username de TrainingPeaks (Cuenta TrainingPeaks)
    tp_name = Column(String, nullable=True)  # Nombre del atleta en TrainingPeaks
    training_status = Column(String(50), server_default="Por generar", index=True)
    
    # Perfil Deportivo y Fisico
    discipline = Column(String(100), nullable=True)
    level = Column(String(100), nullable=True)
    goal = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    experience = Column(String(255), nullable=True)
    
    # Datos Personales (Flat)
    consent = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True) 
    gender = Column(String, nullable=True)
    country = Column(String, nullable=True)
    state = Column(String, nullable=True)
    city = Column(String, nullable=True)
    instagram = Column(String, nullable=True)
    emergency_contact_name = Column(String, nullable=True)
    emergency_contact_phone = Column(String, nullable=True)
    current_weight = Column(String, nullable=True)
    target_weight = Column(String, nullable=True)
    max_historical_weight = Column(String, nullable=True)
    height = Column(String, nullable=True)
    
    # Datos Medicos (Flat)
    diseases_conditions = Column(String, nullable=True)
    acute_injury_disease = Column(String, nullable=True)
    acute_injury_type = Column(String, nullable=True)
    has_fractures_sprains_history = Column(String, nullable=True)
    fracture_history = Column(String, nullable=True)
    medications = Column(String, nullable=True)
    supplements = Column(String, nullable=True)
    smoker = Column(String, nullable=True)
    alcohol_consumption = Column(String, nullable=True)
    daily_sleep_hours = Column(String, nullable=True)
    sleep_quality = Column(String, nullable=True)
    meals_per_day = Column(String, nullable=True)
    diet_type = Column(String, nullable=True)
    diet_description = Column(String, nullable=True)
    
    # Datos Deportivos Detallados (Flat)
    athlete_type = Column(String, nullable=True)
    disciplines_count = Column(String, nullable=True)
    previous_sports = Column(String, nullable=True)
    running_experience_time = Column(String, nullable=True)
    cycling_experience_time = Column(String, nullable=True)
    swimming_experience_time = Column(String, nullable=True)
    short_term_goal = Column(String, nullable=True)
    medium_term_goal = Column(String, nullable=True)
    long_term_goal = Column(String, nullable=True)
    
    # Records (Flat)
    best_time_5k = Column(String, nullable=True)
    best_time_10k = Column(String, nullable=True)
    # best_time_10k_duplicado = Column(String, nullable=True) # Removido el duplicado
    best_time_21k = Column(String, nullable=True)
    marathon_time = Column(String, nullable=True)
    triathlon_distance = Column(String, nullable=True)
    triathlon_time = Column(String, nullable=True)
    triathlon_place = Column(String, nullable=True)
    longest_run_distance = Column(String, nullable=True)
    longest_run_event = Column(String, nullable=True)
    longest_run_date = Column(String, nullable=True)
    
    # Preferencias de Entrenamiento (Flat)
    training_frequency_weekly = Column(String, nullable=True)
    training_hours_weekly = Column(String, nullable=True)
    preferred_schedule = Column(String, nullable=True)
    schedule = Column(String, nullable=True)
    preferred_rest_day = Column(String, nullable=True)
    sacrifice_rest_day = Column(String, nullable=True)
    main_event = Column(String, nullable=True)
    event_type = Column(String, nullable=True)
    time_to_event = Column(String, nullable=True)
    secondary_events = Column(String, nullable=True)
    
    # Equipamiento (Flat)
    watch_brand_model = Column(String, nullable=True)
    has_watch = Column(String, nullable=True)
    watch_brand = Column(String, nullable=True)
    sensors_owned = Column(String, nullable=True)
    has_pool_access = Column(String, nullable=True)
    has_smart_trainer = Column(String, nullable=True)
    
    # Otros (Flat)
    reason_for_sport = Column(String, nullable=True)
    annual_goals = Column(String, nullable=True)
    preferred_communication_channels = Column(String, nullable=True)
    whatsapp_group_interest = Column(String, nullable=True)
    discount = Column(String, nullable=True)
    client_status = Column(String, nullable=True)
    old_registration_date = Column(String, nullable=True)
    pending_payment = Column(String, nullable=True)
    form_link = Column(String, nullable=True)
    weight_objective_category = Column(String, nullable=True)
    bad_habits_percentage = Column(String, nullable=True)
    registration_date = Column(DateTime(timezone=True), nullable=True)
    training_start_date = Column(Date, nullable=True)  # Fecha ISO 8601 desde Airtable

    # Datos Generados por App (JSON se mantiene para estructuras complejas generadas internamente)
    performance = Column(JSON, nullable=True) 
    
    def __repr__(self):
        return f"<Athlete(id={self.id}, name={self.name}, training_status={self.training_status})>"



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

