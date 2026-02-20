"""
Entidades de dominio para metricas de entrenamiento computadas.

Define las estructuras de datos para almacenar metricas preprocesadas
del historial de entrenamientos, optimizadas para consumo por el LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import List, Dict, Any, Optional


@dataclass
class ComputedMetrics:
    """
    Metricas preprocesadas del historial de entrenamientos.
    
    Estas metricas se calculan una vez al sincronizar el historial de TP
    y se almacenan en AthleteModel.performance.computed_metrics.
    
    El objetivo es reducir el contexto enviado al LLM de ~3000 tokens
    a ~500 tokens manteniendo la informacion relevante.
    """
    
    # Metadata de la computacion
    computed_at: datetime
    period_days: int
    period_start: date
    period_end: date
    
    # Totales del periodo
    total_workouts: int
    total_completed: int
    total_skipped: int
    total_hours: float
    total_distance_km: float
    total_tss: int
    total_elevation_m: int
    
    # Promedios semanales
    avg_weekly_hours: float
    avg_weekly_distance: float
    avg_weekly_tss: float
    avg_workouts_per_week: float
    avg_workout_duration_min: float
    
    # Carga de entrenamiento (Modelo Banister)
    ctl: float  # Chronic Training Load (fitness) - ventana 42 dias
    atl: float  # Acute Training Load (fatigue) - ventana 7 dias
    tsb: float  # Training Stress Balance (form) = CTL - ATL
    ramp_rate: float  # Cambio semanal de CTL (TSS/dia/semana)
    
    # Adherencia al plan
    adherence_rate: float  # % de workouts completados vs planeados
    consistency_score: float  # Regularidad de entrenamiento (0-1)
    
    # Distribucion de intensidad (regla 80/20)
    pct_easy: float      # % en Z1-Z2 (IF < 0.75)
    pct_moderate: float  # % en Z3 (IF 0.75-0.90)
    pct_hard: float      # % en Z4-Z5 (IF > 0.90)
    
    # Patrones detectados
    preferred_workout_days: List[str] = field(default_factory=list)
    typical_rest_day: Optional[str] = None
    longest_streak: int = 0  # Dias consecutivos entrenando
    longest_gap: int = 0     # Dias consecutivos sin entrenar
    
    # Tendencias (comparando ultimas 4 semanas vs 4 anteriores)
    volume_trend: str = "stable"     # "increasing", "stable", "decreasing"
    intensity_trend: str = "stable"  # "increasing", "stable", "decreasing"
    
    # Distribucion por tipo de workout
    distribution_by_type: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte las metricas a diccionario para persistencia en JSON.
        Maneja la serializacion de dates y datetimes.
        """
        data = asdict(self)
        # Convertir datetime/date a ISO strings
        data['computed_at'] = self.computed_at.isoformat()
        data['period_start'] = self.period_start.isoformat()
        data['period_end'] = self.period_end.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComputedMetrics":
        """
        Crea una instancia desde un diccionario (deserializacion).
        """
        # Parsear strings ISO a datetime/date
        if isinstance(data.get('computed_at'), str):
            data['computed_at'] = datetime.fromisoformat(data['computed_at'])
        if isinstance(data.get('period_start'), str):
            data['period_start'] = date.fromisoformat(data['period_start'])
        if isinstance(data.get('period_end'), str):
            data['period_end'] = date.fromisoformat(data['period_end'])
        
        return cls(**data)
    
    def get_load_status(self) -> str:
        """
        Retorna una descripcion del estado de carga actual.
        Util para mostrar en UI o incluir en prompts.
        """
        if self.tsb > 10:
            return "fresh"  # Bien descansado, listo para intensidad
        elif self.tsb > -10:
            return "neutral"  # Balance normal
        elif self.tsb > -20:
            return "fatigued"  # Fatiga moderada
        else:
            return "overtrained"  # Riesgo de sobreentrenamiento
    
    def get_polarization_status(self) -> str:
        """
        Evalua si la distribucion de intensidad sigue la regla 80/20.
        """
        if self.pct_easy >= 0.75:
            return "well_polarized"
        elif self.pct_easy >= 0.65:
            return "moderately_polarized"
        else:
            return "not_polarized"
