"""
Servicios de aplicacion.

Contiene la logica de negocio reutilizable que no pertenece
a un caso de uso especifico.
"""
from app.application.services.history_processor import HistoryProcessor
from app.application.services.context_builder import AthleteContextBuilder
from app.application.services.tp_data_normalizer import (
    TPDataNormalizer,
    WorkoutValidationReport,
    HistoryValidationSummary,
)
from app.application.services.alert_evaluators import (
    register_default_alerts,
    HighRampRateAlert,
    LowAdherenceAlert,
    NegativeTSBAlert,
    PolarizationAlert,
    LongGapAlert,
)

__all__ = [
    # Procesamiento de historial
    "HistoryProcessor",
    "TPDataNormalizer",
    "WorkoutValidationReport",
    "HistoryValidationSummary",
    # Contexto LLM
    "AthleteContextBuilder",
    # Alertas
    "register_default_alerts",
    "HighRampRateAlert",
    "LowAdherenceAlert",
    "NegativeTSBAlert",
    "PolarizationAlert",
    "LongGapAlert",
]
