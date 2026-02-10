"""
DTOs para metricas computadas y alertas.

Define las estructuras de datos para exponer metricas y alertas
a traves de la API REST.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field


class AlertDTO(BaseModel):
    """
    DTO para alertas en respuestas de API.
    
    Representa una alerta activa del atleta con toda la informacion
    necesaria para mostrar en UI y tomar acciones.
    """
    
    id: str = Field(..., description="Identificador unico de la alerta")
    category: str = Field(..., description="Categoria: load, recovery, adherence, performance, health")
    severity: str = Field(..., description="Severidad: info, warning, critical")
    title: str = Field(..., description="Titulo corto para UI")
    message: str = Field(..., description="Mensaje descriptivo")
    recommendation: str = Field(..., description="Accion recomendada")
    value: float = Field(..., description="Valor actual que disparo la alerta")
    threshold: float = Field(..., description="Umbral configurado")
    created_at: datetime = Field(..., description="Fecha de creacion")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Datos adicionales")

    class Config:
        from_attributes = True


class ComputedMetricsDTO(BaseModel):
    """
    DTO para metricas computadas en respuestas de API.
    
    Contiene todas las metricas preprocesadas del historial de
    entrenamientos del atleta.
    """
    
    # Metadata
    computed_at: datetime = Field(..., description="Fecha de computacion")
    period_days: int = Field(..., description="Dias del periodo analizado")
    period_start: date = Field(..., description="Inicio del periodo")
    period_end: date = Field(..., description="Fin del periodo")
    
    # Totales
    total_workouts: int = Field(0, description="Total de workouts en el periodo")
    total_completed: int = Field(0, description="Workouts completados")
    total_skipped: int = Field(0, description="Workouts omitidos")
    total_hours: float = Field(0.0, description="Horas totales de entrenamiento")
    total_distance_km: float = Field(0.0, description="Distancia total en km")
    total_tss: int = Field(0, description="TSS total acumulado")
    total_elevation_m: int = Field(0, description="Elevacion total en metros")
    
    # Promedios semanales
    avg_weekly_hours: float = Field(0.0, description="Horas promedio por semana")
    avg_weekly_distance: float = Field(0.0, description="Distancia promedio semanal en km")
    avg_weekly_tss: float = Field(0.0, description="TSS promedio semanal")
    avg_workouts_per_week: float = Field(0.0, description="Entrenamientos por semana")
    avg_workout_duration_min: float = Field(0.0, description="Duracion promedio por workout")
    
    # Carga (Modelo Banister)
    ctl: float = Field(0.0, description="Chronic Training Load (fitness)")
    atl: float = Field(0.0, description="Acute Training Load (fatigue)")
    tsb: float = Field(0.0, description="Training Stress Balance (form)")
    ramp_rate: float = Field(0.0, description="Cambio semanal de CTL")
    
    # Adherencia
    adherence_rate: float = Field(0.0, description="Tasa de adherencia (0-1)")
    consistency_score: float = Field(0.0, description="Score de consistencia (0-1)")
    
    # Distribucion de intensidad
    pct_easy: float = Field(0.0, description="Porcentaje en Z1-Z2")
    pct_moderate: float = Field(0.0, description="Porcentaje en Z3")
    pct_hard: float = Field(0.0, description="Porcentaje en Z4-Z5")
    
    # Patrones
    preferred_workout_days: List[str] = Field(default_factory=list, description="Dias preferidos")
    typical_rest_day: Optional[str] = Field(None, description="Dia de descanso tipico")
    longest_streak: int = Field(0, description="Dias consecutivos entrenando")
    longest_gap: int = Field(0, description="Dias consecutivos sin entrenar")
    
    # Tendencias
    volume_trend: str = Field("stable", description="Tendencia de volumen")
    intensity_trend: str = Field("stable", description="Tendencia de intensidad")
    
    # Distribucion por tipo
    distribution_by_type: Dict[str, float] = Field(default_factory=dict, description="% por tipo")
    
    # Alertas activas
    active_alerts: List[AlertDTO] = Field(default_factory=list, description="Alertas activas")

    class Config:
        from_attributes = True


class MetricsRecomputeResponseDTO(BaseModel):
    """
    DTO para respuesta de recomputacion de metricas.
    """
    
    success: bool = Field(..., description="Si la operacion fue exitosa")
    message: str = Field(..., description="Mensaje descriptivo")
    athlete_id: str = Field(..., description="ID del atleta")
    computed_at: datetime = Field(..., description="Timestamp de la computacion")
    alerts_count: int = Field(0, description="Numero de alertas activas")

    class Config:
        from_attributes = True


class AlertsListResponseDTO(BaseModel):
    """
    DTO para lista de alertas con filtros aplicados.
    """
    
    athlete_id: str = Field(..., description="ID del atleta")
    total_alerts: int = Field(0, description="Total de alertas")
    alerts: List[AlertDTO] = Field(default_factory=list, description="Lista de alertas")
    filters_applied: Dict[str, str] = Field(default_factory=dict, description="Filtros aplicados")

    class Config:
        from_attributes = True
