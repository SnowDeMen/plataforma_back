"""
DTOs para operaciones de planes de entrenamiento.
Define estructuras para generacion, visualizacion y gestion de planes de 4 semanas.
"""
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field


class AthleteInfoDTO(BaseModel):
    """
    Informacion del atleta para contexto de generacion.
    Incluye datos personales, medicos y deportivos.
    """
    
    age: Optional[int] = Field(None, description="Edad del atleta")
    discipline: Optional[str] = Field(None, description="Disciplina principal")
    level: Optional[str] = Field(None, description="Nivel de competencia")
    goal: Optional[str] = Field(None, description="Objetivo principal")
    experience: Optional[str] = Field(None, description="Experiencia deportiva")
    
    personal: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Informacion personal: genero, BMI, sesiones/semana, etc."
    )
    medica: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Informacion medica: enfermedades, sueno, dieta"
    )
    deportiva: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Informacion deportiva: records, equipo, evento objetivo"
    )
    performance: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Historial de entrenamientos recientes"
    )
    computed_metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metricas preprocesadas: CTL, ATL, TSB, adherencia, distribucion"
    )

    class Config:
        from_attributes = True


class PlanGenerationRequestDTO(BaseModel):
    """DTO para solicitar la generacion de un plan de entrenamiento."""
    
    athlete_id: str = Field(..., description="ID del atleta")
    athlete_name: str = Field(..., description="Nombre del atleta")
    athlete_info: AthleteInfoDTO = Field(..., description="Informacion completa del atleta")
    start_date: Optional[date] = Field(None, description="Fecha de inicio del plan")
    weeks: int = Field(default=4, ge=1, le=12, description="Numero de semanas del plan")

    class Config:
        from_attributes = True


class PlanWorkoutDTO(BaseModel):
    """DTO para un workout individual dentro del plan."""
    
    day: int = Field(..., ge=1, le=28, description="Dia del plan (1-28 para 4 semanas)")
    week: int = Field(..., ge=1, le=4, description="Semana del plan (1-4)")
    date: Optional[str] = Field(None, description="Fecha en formato YYYY-MM-DD")
    
    workout_type: str = Field(..., description="Tipo: Run, Bike, Swim, Strength, Day off, etc.")
    title: str = Field(..., description="Titulo del workout")
    description: Optional[str] = Field(None, description="Descripcion breve del objetivo")
    pre_activity_comments: Optional[str] = Field(
        None, 
        description="Instrucciones detalladas para el atleta"
    )
    
    # Valores planeados
    duration: Optional[str] = Field(None, description="Duracion en formato h:m:s")
    distance: Optional[str] = Field(None, description="Distancia en km")
    tss: Optional[int] = Field(None, description="Training Stress Score")
    intensity_factor: Optional[float] = Field(None, alias="if", description="Intensity Factor")
    average_pace: Optional[str] = Field(None, description="Ritmo promedio")
    elevation_gain: Optional[int] = Field(None, description="Desnivel en metros")
    calories: Optional[int] = Field(None, description="Calorias estimadas")

    class Config:
        from_attributes = True
        populate_by_name = True


class WeekSummaryDTO(BaseModel):
    """DTO para resumen de una semana del plan."""
    
    week: int = Field(..., description="Numero de semana")
    total_duration: str = Field(..., description="Duracion total de la semana")
    total_distance: str = Field(..., description="Distancia total")
    total_tss: int = Field(..., description="TSS total de la semana")
    workout_count: int = Field(..., description="Cantidad de workouts")
    rest_days: int = Field(..., description="Dias de descanso")
    focus: Optional[str] = Field(None, description="Enfoque de la semana")
    workouts: List[PlanWorkoutDTO] = Field(default_factory=list, description="Workouts de la semana")

    class Config:
        from_attributes = True


class TrainingPlanDTO(BaseModel):
    """DTO para un plan de entrenamiento completo."""
    
    id: int = Field(..., description="ID del plan")
    athlete_id: str = Field(..., description="ID del atleta")
    athlete_name: str = Field(..., description="Nombre del atleta")
    status: str = Field(..., description="Estado: pending, generating, review, active, applied")
    
    weeks_count: int = Field(default=4, description="Numero de semanas")
    start_date: Optional[date] = Field(None, description="Fecha de inicio")
    end_date: Optional[date] = Field(None, description="Fecha de fin")
    
    summary: Optional[str] = Field(None, description="Resumen general del plan")
    total_tss: Optional[int] = Field(None, description="TSS total del plan")
    total_distance: Optional[str] = Field(None, description="Distancia total")
    total_duration: Optional[str] = Field(None, description="Duracion total")
    
    weeks: List[WeekSummaryDTO] = Field(default_factory=list, description="Semanas del plan")
    workouts: List[PlanWorkoutDTO] = Field(default_factory=list, description="Todos los workouts")
    
    created_at: Optional[datetime] = Field(None, description="Fecha de creacion")
    updated_at: Optional[datetime] = Field(None, description="Ultima actualizacion")
    approved_at: Optional[datetime] = Field(None, description="Fecha de aprobacion")

    class Config:
        from_attributes = True


class PlanProgressDTO(BaseModel):
    """DTO para el progreso de generacion de un plan (WebSocket)."""
    
    plan_id: int = Field(..., description="ID del plan en generacion")
    status: str = Field(..., description="Estado actual")
    progress: int = Field(default=0, ge=0, le=100, description="Porcentaje de progreso")
    current_week: Optional[int] = Field(None, description="Semana actual en generacion")
    current_workout: Optional[int] = Field(None, description="Workout actual")
    total_workouts: int = Field(default=28, description="Total de workouts a generar")
    message: str = Field(default="", description="Mensaje de estado")
    
    class Config:
        from_attributes = True


class PlanListItemDTO(BaseModel):
    """DTO para item en lista de planes (vista resumida)."""
    
    id: int = Field(..., description="ID del plan")
    athlete_id: str = Field(..., description="ID del atleta")
    athlete_name: str = Field(..., description="Nombre del atleta")
    status: str = Field(..., description="Estado del plan")
    weeks_count: int = Field(default=4, description="Numero de semanas")
    start_date: Optional[date] = Field(None, description="Fecha de inicio")
    total_tss: Optional[int] = Field(None, description="TSS total")
    workout_count: int = Field(default=0, description="Cantidad de workouts")
    created_at: Optional[datetime] = Field(None, description="Fecha de creacion")

    class Config:
        from_attributes = True


class PlanApprovalDTO(BaseModel):
    """DTO para aprobar o rechazar un plan."""
    
    approved: bool = Field(..., description="True para aprobar, False para rechazar")
    feedback: Optional[str] = Field(None, description="Comentarios del coach")

    class Config:
        from_attributes = True


class PlanApplyRequestDTO(BaseModel):
    """
    DTO para aprobar y aplicar un plan a TrainingPeaks.

    Importante:
    - El frontend envía el JSON de workouts (derivado del plan) para que el backend
      ejecute un flujo determinístico (Selenium directo).
    - El backend puede usar `plan.start_date` para completar fechas faltantes si aplica.
    """

    workouts: List[PlanWorkoutDTO] = Field(
        default_factory=list,
        description="Lista de workouts a subir/aplicar en TrainingPeaks"
    )
    folder_name: Optional[str] = Field(
        default=None,
        description="Carpeta destino en Workout Library (opcional)"
    )

    class Config:
        from_attributes = True


class PlanModifyRequestDTO(BaseModel):
    """
    DTO para solicitar la modificacion de un plan existente.
    Permite modificar un dia, una semana, o el plan completo.
    Incluye opciones para forzar cambios riesgosos o usar alternativas seguras.
    """
    
    scope: str = Field(
        ..., 
        description="Alcance de la modificacion: 'day', 'week', o 'plan'"
    )
    target: Optional[Dict[str, Any]] = Field(
        None,
        description="Detalles del elemento a modificar (week num, day num, workout data)"
    )
    prompt: str = Field(
        ..., 
        min_length=5,
        description="Instrucciones del usuario para la modificacion"
    )
    force_apply: bool = Field(
        default=False,
        description="Si True, aplica el cambio aunque sea riesgoso"
    )
    use_safe_alternative: bool = Field(
        default=False,
        description="Si True, aplica la alternativa segura propuesta previamente"
    )

    class Config:
        from_attributes = True


class PlanModifyChangeDTO(BaseModel):
    """DTO para describir un cambio realizado en el plan."""
    
    type: str = Field(..., description="Tipo de cambio: day, week, plan")
    target: str = Field(..., description="Identificador del elemento modificado")
    original: str = Field(..., description="Resumen de lo que habia antes")
    new: str = Field(..., description="Resumen de lo que hay ahora")
    reason: str = Field(..., description="Razon del cambio")

    class Config:
        from_attributes = True


class SafeAlternativeWorkoutDTO(BaseModel):
    """DTO para preview del workout alternativo seguro."""
    
    title: str = Field(..., description="Titulo del workout alternativo")
    workout_type: str = Field(..., description="Tipo de workout")
    duration: Optional[str] = Field(None, description="Duracion si aplica")
    tss: Optional[int] = Field(None, description="TSS estimado")
    description: Optional[str] = Field(None, description="Descripcion breve")

    class Config:
        from_attributes = True


class SafeAlternativeDTO(BaseModel):
    """DTO para la alternativa segura propuesta por el agente."""
    
    description: str = Field(..., description="Descripcion de la alternativa segura")
    workout_preview: Optional[SafeAlternativeWorkoutDTO] = Field(
        None, 
        description="Preview del workout alternativo"
    )

    class Config:
        from_attributes = True


class ModificationHistoryEntryDTO(BaseModel):
    """DTO para una entrada en el historial de modificaciones."""
    
    id: int = Field(..., description="ID secuencial de la modificacion")
    timestamp: str = Field(..., description="Timestamp ISO de la modificacion")
    scope: str = Field(..., description="Alcance: day, week, plan")
    target: Optional[Dict[str, Any]] = Field(None, description="Elemento modificado")
    user_prompt: str = Field(..., description="Solicitud original del usuario")
    summary: str = Field(..., description="Resumen del cambio aplicado")
    changes: List[PlanModifyChangeDTO] = Field(
        default_factory=list, 
        description="Cambios realizados"
    )
    decision: str = Field(
        ..., 
        description="Tipo de decision: direct, forced, alternative"
    )
    had_risk_warning: bool = Field(
        default=False, 
        description="Si hubo advertencia de riesgo"
    )
    risk_warning: Optional[str] = Field(
        None, 
        description="Advertencia de riesgo si aplica"
    )
    forced_by_user: bool = Field(
        default=False, 
        description="Si el usuario forzo el cambio"
    )
    used_safe_alternative: bool = Field(
        default=False, 
        description="Si se uso la alternativa segura"
    )

    class Config:
        from_attributes = True


class PlanModifyResponseDTO(BaseModel):
    """
    DTO para la respuesta de modificacion de un plan.
    Puede indicar que se requiere confirmacion si detecta riesgo.
    """
    
    success: bool = Field(..., description="Si la operacion fue exitosa")
    message: str = Field(..., description="Mensaje descriptivo del resultado")
    
    # Campos para confirmacion de riesgo
    requires_confirmation: bool = Field(
        default=False,
        description="Si True, el cambio es riesgoso y requiere confirmacion"
    )
    risk_warning: Optional[str] = Field(
        None,
        description="Advertencia de riesgo para el usuario"
    )
    risk_category: Optional[str] = Field(
        None,
        description="Categoria del riesgo detectado"
    )
    user_request_summary: Optional[str] = Field(
        None,
        description="Resumen de lo que el usuario solicito"
    )
    safe_alternative: Optional[SafeAlternativeDTO] = Field(
        None,
        description="Alternativa segura propuesta"
    )
    
    # Campos cuando se aplica el cambio
    summary: Optional[str] = Field(None, description="Resumen de los cambios realizados")
    changes: List[PlanModifyChangeDTO] = Field(
        default_factory=list, 
        description="Lista detallada de cambios"
    )
    plan: Optional[TrainingPlanDTO] = Field(
        None, 
        description="Plan actualizado completo"
    )
    decision: Optional[str] = Field(
        None,
        description="Tipo de decision: direct, forced, alternative"
    )
    had_risk_warning: bool = Field(
        default=False,
        description="Si hubo advertencia de riesgo en esta modificacion"
    )

    class Config:
        from_attributes = True


class PlanModificationHistoryDTO(BaseModel):
    """DTO para el historial completo de modificaciones de un plan."""
    
    plan_id: int = Field(..., description="ID del plan")
    athlete_name: str = Field(..., description="Nombre del atleta")
    modifications: List[ModificationHistoryEntryDTO] = Field(
        default_factory=list,
        description="Lista de todas las modificaciones"
    )
    total_modifications: int = Field(
        default=0,
        description="Total de modificaciones realizadas"
    )
    forced_changes_count: int = Field(
        default=0,
        description="Cantidad de cambios forzados por el usuario"
    )

    class Config:
        from_attributes = True


class ApplyTPPlanRequestDTO(BaseModel):
    """
    Solicitud para aplicar un Training Plan existente de TrainingPeaks a un atleta.
    
    Este endpoint es para testing del flujo de Selenium que aplica
    planes de entrenamiento predefinidos en TrainingPeaks.
    """
    
    plan_name: str = Field(
        ..., 
        min_length=1,
        description="Nombre del plan en TrainingPeaks (ej: 'Test')"
    )
    athlete_name: str = Field(
        ..., 
        min_length=1,
        description="Nombre del atleta en TrainingPeaks"
    )
    start_date: date = Field(
        ..., 
        description="Fecha de inicio del plan (ISO 8601)"
    )

    class Config:
        from_attributes = True


class ApplyTPPlanResponseDTO(BaseModel):
    """Respuesta de aplicar un Training Plan de TrainingPeaks."""
    
    success: bool = Field(..., description="Si la operacion fue exitosa")
    message: str = Field(..., description="Mensaje descriptivo del resultado")
    plan_name: str = Field(..., description="Nombre del plan aplicado")
    athlete_name: str = Field(..., description="Nombre del atleta")
    start_date: str = Field(..., description="Fecha de inicio aplicada")

    class Config:
        from_attributes = True
