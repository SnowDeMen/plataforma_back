"""
Configuración de base de datos.

Importa todos los modelos para que se registren con Base
antes de crear las tablas.
"""
from app.infrastructure.database.models import (
    AgentModel,
    ChatSessionModel,
    ConversationModel,
    TrainingModel,
    TrainingPlanModel,
    AthleteModel
)

