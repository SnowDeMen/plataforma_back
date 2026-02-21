"""
DTOs relacionados con atletas.
Definen la estructura de datos para transferir informacion de atletas.
Incluye DTOs para sincronizacion con Airtable y para gestion interna de planes.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class AirtableAthleteDTO(BaseModel):
    """
    DTO para representar un atleta sincronizado de Airtable (perfil completo).
    Mapea la estructura plana de la tabla 'airtable.athletes'.
    """
    id: str = Field(..., description="ID del registro de Airtable")
    airtable_id: Optional[str] = Field(None, description="ID del registro de Airtable (redundante)")
    name: str = Field(..., description="Nombre completo del atleta")
    email: Optional[str] = Field(None, description="Email del atleta")
    training_status: Optional[str] = Field("Por generar", description="Estado del entrenamiento (Por generar, etc)")
    client_status: Optional[str] = Field(None, description="Estado administrativo (ACTIVO, etc)")
    
    # Campos principales
    discipline: Optional[str] = None
    level: Optional[str] = None
    goal: Optional[str] = None
    age: Optional[int] = None
    experience: Optional[str] = None
    
    # Estructuras complejas (JSON)
    personal: Optional[Dict[str, Any]] = None
    medica: Optional[Dict[str, Any]] = None
    deportiva: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class RecordsDTO(BaseModel):
    """DTO para records personales del atleta."""
    distanciaMaxima: Optional[str] = None
    dist5k: Optional[str] = None
    dist10k: Optional[str] = None
    dist21k: Optional[str] = None
    maraton: Optional[str] = None
    triatlon: Optional[str] = None
    
    class Config:
        from_attributes = True


class PersonalInfoDTO(BaseModel):
    """DTO para informacion personal del atleta."""
    nombreCompleto: Optional[str] = None
    genero: Optional[str] = None
    bmi: Optional[float] = None
    tipoAtleta: Optional[str] = None
    sesionesSemanales: Optional[str] = None
    horasSemanales: Optional[str] = None
    horarioPreferido: Optional[str] = None
    diaDescanso: Optional[str] = None
    
    class Config:
        from_attributes = True


class MedicaInfoDTO(BaseModel):
    """DTO para informacion medica del atleta."""
    enfermedades: Optional[str] = None
    lesionAguda: Optional[str] = None
    tipoLesion: Optional[str] = None
    fuma: Optional[str] = None
    alcohol: Optional[str] = None
    horasSueno: Optional[int] = None
    calidadSueno: Optional[str] = None
    dieta: Optional[str] = None
    
    class Config:
        from_attributes = True


class WorkoutDTO(BaseModel):
    """DTO para un entrenamiento individual."""
    fecha: str
    tipo: str
    hora: Optional[str] = None
    estado: str
    duracionPlan: Optional[str] = None
    duracionComp: Optional[str] = None
    distanciaPlan: Optional[str] = None
    distanciaComp: Optional[str] = None
    tssPlan: Optional[int] = None
    tssComp: Optional[int] = None
    ifPlan: Optional[float] = None
    ifComp: Optional[float] = None
    ritmoPlan: Optional[str] = None
    ritmoComp: Optional[str] = None
    fcMin: Optional[int] = None
    fcMed: Optional[int] = None
    fcMax: Optional[int] = None
    cadencia: Optional[int] = None
    calorias: Optional[int] = None
    elevacion: Optional[int] = None
    estructura: Optional[str] = None
    notas: Optional[str] = None
    
    class Config:
        from_attributes = True


class DeportivaInfoDTO(BaseModel):
    """DTO para informacion deportiva del atleta."""
    tiempoPracticando: Optional[str] = None
    records: Optional[RecordsDTO] = None
    medidores: Optional[List[str]] = None
    equipo: Optional[str] = None
    equipoDisponible: Optional[str] = None
    eventoObjetivo: Optional[str] = None
    diasParaEvento: Optional[int] = None
    dedicacion: Optional[str] = None
    
    class Config:
        from_attributes = True


class PerformanceSummaryDTO(BaseModel):
    """DTO para resumen de desempeno del atleta."""
    periodo: Optional[str] = None
    tiempoTotal: Optional[str] = None
    distanciaTotal: Optional[str] = None
    tssTotal: Optional[int] = None
    entrenamientosCompletados: Optional[int] = None
    entrenamientosPlaneados: Optional[int] = None
    workouts: Optional[List[WorkoutDTO]] = None
    
    class Config:
        from_attributes = True


class AthleteDTO(BaseModel):
    """DTO completo para un atleta (Dominio/Plan)."""
    id: str
    name: str
    last_name: Optional[str] = None
    age: Optional[int] = None
    discipline: Optional[str] = None
    level: Optional[str] = None
    goal: Optional[str] = None
    training_status: str = "Por generar"
    client_status: Optional[str] = None
    experience: Optional[str] = None
    tp_username: Optional[str] = None  # Cuenta TrainingPeaks (desde Airtable)
    tp_name: Optional[str] = None      # Nombre validado en TrainingPeaks
    personal: Optional[PersonalInfoDTO] = None
    medica: Optional[MedicaInfoDTO] = None
    deportiva: Optional[DeportivaInfoDTO] = None
    performance: Optional[PerformanceSummaryDTO] = None
    
    class Config:
        from_attributes = True


class AthleteListItemDTO(BaseModel):
    """DTO resumido para listas de atletas."""
    id: str
    name: str
    last_name: Optional[str] = None
    age: Optional[int] = None
    discipline: Optional[str] = None
    level: Optional[str] = None
    training_status: Optional[str] = "Por generar"
    client_status: Optional[str] = None
    goal: Optional[str] = None
    
    class Config:
        from_attributes = True


class AthleteUpdateDTO(BaseModel):
    """DTO para actualizar un atleta existente."""
    name: Optional[str] = None
    age: Optional[int] = None
    discipline: Optional[str] = None
    level: Optional[str] = None
    goal: Optional[str] = None
    training_status: Optional[str] = None
    client_status: Optional[str] = None
    experience: Optional[str] = None
    personal: Optional[Dict[str, Any]] = None
    medica: Optional[Dict[str, Any]] = None
    deportiva: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class AthleteStatusUpdateDTO(BaseModel):
    """DTO para cambiar solo el status de un atleta."""
    training_status: str = Field(
        ..., 
        description="Nuevo status del entrenamiento",
        pattern="^(Por generar|Por revisar|Plan activo)$"
    )
    
    class Config:
        from_attributes = True


class AthleteCreateDTO(BaseModel):
    """DTO para crear un nuevo atleta."""
    id: str = Field(..., description="ID unico del atleta")
    name: str = Field(..., description="Nombre del atleta")
    age: Optional[int] = None
    discipline: Optional[str] = None
    level: Optional[str] = None
    goal: Optional[str] = None
    class Config:
        from_attributes = True
