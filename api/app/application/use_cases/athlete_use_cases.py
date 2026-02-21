"""
Casos de uso para la gestion de atletas.

Implementa la logica de negocio para operaciones con atletas,
siguiendo el patron de arquitectura limpia.
"""
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from datetime import datetime

from app.application.dto.athlete_dto import (
    AthleteDTO,
    AthleteListItemDTO,
    AthleteUpdateDTO,
    AthleteStatusUpdateDTO,
    AthleteCreateDTO,
    PersonalInfoDTO,
    MedicaInfoDTO,
    DeportivaInfoDTO,
    RecordsDTO,
    PerformanceSummaryDTO
)
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.shared.exceptions.domain import EntityNotFoundException


class AthleteNotFoundException(EntityNotFoundException):
    """Excepcion cuando no se encuentra un atleta."""
    
    def __init__(self, athlete_id: str):
        super().__init__(
            message=f"Atleta con ID '{athlete_id}' no encontrado",
            error_code="ATHLETE_NOT_FOUND",
            details={"athlete_id": athlete_id}
        )
        self.status_code = 404


class AthleteUseCases:
    """
    Casos de uso para operaciones con atletas.
    
    Encapsula la logica de negocio relacionada con la gestion
    de atletas, incluyendo listado, consulta, actualizacion y seed.
    """

    def __init__(self, db: AsyncSession):
        """
        Inicializa los casos de uso con una sesion de base de datos.
        
        Args:
            db: Sesion asincrona de SQLAlchemy
        """
        self.db = db
        self.repository = AthleteRepository(db)

    async def list_athletes(
        self,
        training_status: Optional[str] = None,
        client_status: Optional[str] = None,
        discipline: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AthleteListItemDTO]:
        """
        Lista atletas con filtros opcionales.
        
        Args:
            status: Filtrar por status
            discipline: Filtrar por disciplina
            limit: Maximo de resultados
            offset: Desplazamiento para paginacion
            
        Returns:
            Lista de AthleteListItemDTO
        """
        athletes = await self.repository.get_all(
            training_status=training_status,
            client_status=client_status,
            discipline=discipline,
            limit=limit,
            offset=offset
        )
        
        return [
            AthleteListItemDTO(
                id=a.id,
                name=a.name,
                last_name=a.last_name,
                age=a.age,
                discipline=a.discipline,
                level=a.level,
                training_status=a.training_status,
                client_status=a.client_status,
                goal=a.goal
            )
            for a in athletes
        ]

    def _calculate_age(self, dob_str: Optional[str]) -> Optional[int]:
        """Calcula edad basada en fecha de nacimiento (YYYY-MM-DD)."""
        if not dob_str:
            return None
        try:
            # Intentar parsear fecha ISO (YYYY-MM-DD)
            dob = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
            today = datetime.now().date()
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except (ValueError, TypeError):
            return None

    def _calculate_bmi(self, weight_str: Optional[str], height_str: Optional[str]) -> Optional[float]:
        """Calcula BMI (IMC)."""
        if not weight_str or not height_str:
            return None
        try:
            # Limpiar strings (e.g. "70 kg", "1.75 m")
            w = float(''.join(c for c in weight_str if c.isdigit() or c == '.'))
            h = float(''.join(c for c in height_str if c.isdigit() or c == '.'))
            
            # Asumir altura en cm si es > 3, convertir a metros
            if h > 3: 
                h = h / 100.0
                
            if h <= 0: return None
            
            bmi = w / (h * h)
            return round(bmi, 2)
        except (ValueError, ZeroDivisionError):
            return None

    def _clean_airtable_value(self, value: Optional[str]) -> Optional[str]:
        """Limpia valores que vienen de Airtable como listados serializados [\"Valor\"] o {Valor}."""
        if not value:
            return None
        # Quitar corchetes, llaves, comillas y espacios si parece una lista de un elemento
        cleaned = value.strip()
        if cleaned.startswith('[') and cleaned.endswith(']'):
            cleaned = cleaned[1:-1].strip()
        if cleaned.startswith('{') and cleaned.endswith('}'):
            cleaned = cleaned[1:-1].strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        return cleaned

    async def get_athlete(self, athlete_id: str) -> AthleteDTO:
        """
        Obtiene el detalle completo de un atleta.
        """
        athlete = await self.repository.get_by_id(athlete_id)
        
        if not athlete:
            raise AthleteNotFoundException(athlete_id)
            
        # Logica de fallback/calculo para campos faltantes
        age = athlete.age
        if not age:
            age = self._calculate_age(athlete.date_of_birth)
            
        discipline = athlete.discipline
        if not discipline:
            discipline = athlete.athlete_type
            
        bmi = self._calculate_bmi(athlete.current_weight, athlete.height)

        # Fallback para goal (usado en el header del chat)
        goal = athlete.goal
        if not goal:
            goal = athlete.main_event or athlete.short_term_goal
        
        return AthleteDTO(
            id=athlete.id,
            name=athlete.name,
            last_name=athlete.last_name,
            age=age,
            discipline=discipline,
            level=athlete.level,
            goal=goal,
            training_status=athlete.training_status,
            client_status=athlete.client_status,
            experience=athlete.experience,
            tp_username=athlete.tp_username,
            tp_name=athlete.tp_name,
            personal=PersonalInfoDTO(
                nombreCompleto=athlete.full_name,
                genero=athlete.gender,
                tipoAtleta=athlete.athlete_type,
                sesionesSemanales=athlete.training_frequency_weekly,
                horasSemanales=athlete.training_hours_weekly,
                horarioPreferido=athlete.preferred_schedule,
                diaDescanso=athlete.preferred_rest_day,
                bmi=bmi # Campo extra calculado
            ),
            medica=MedicaInfoDTO(
                enfermedades=athlete.diseases_conditions,
                lesionAguda=athlete.acute_injury_disease,
                tipoLesion=athlete.acute_injury_type,
                fuma=self._clean_airtable_value(athlete.smoker),
                alcohol=self._clean_airtable_value(athlete.alcohol_consumption),
                horasSueno=int(athlete.daily_sleep_hours) if athlete.daily_sleep_hours and athlete.daily_sleep_hours.isdigit() else None,
                calidadSueno=self._clean_airtable_value(athlete.sleep_quality),
                dieta=athlete.diet_type
            ),
            deportiva=DeportivaInfoDTO(
                tiempoPracticando=athlete.running_experience_time, # Asumiendo running como principal
                records=RecordsDTO(
                    distanciaMaxima=athlete.longest_run_distance,
                    dist5k=athlete.best_time_5k,
                    dist10k=athlete.best_time_10k,
                    dist21k=athlete.best_time_21k,
                    maraton=athlete.marathon_time,
                    triatlon=athlete.triathlon_distance
                ),
                medidores=[s.strip() for s in athlete.sensors_owned.split(',')] if athlete.sensors_owned else [],
                equipo=athlete.watch_brand_model,
                eventoObjetivo=athlete.main_event,
                diasParaEvento=None, 
                dedicacion=athlete.training_hours_weekly
            ),
            performance=PerformanceSummaryDTO(**athlete.performance) if athlete.performance else None
        )

    async def update_athlete(self, athlete_id: str, dto: AthleteUpdateDTO) -> AthleteDTO:
        """
        Actualiza los datos de un atleta.
        
        Args:
            athlete_id: ID del atleta a actualizar
            dto: Datos a actualizar
            
        Returns:
            AthleteDTO actualizado
            
        Raises:
            AthleteNotFoundException: Si el atleta no existe
        """
        # Verificar existencia
        if not await self.repository.exists(athlete_id):
            raise AthleteNotFoundException(athlete_id)
        
        # Aplanar el DTO para actualizar
        # Nota: Esta logica es simplificada. En un escenario real, deberiamos mapear
        # cada campo del DTO anidado a la columna plana correspondiente.
        # Por ahora, asumimos que si envian 'personal', quieren actualizar campos mapeados manualmente.
        # Como es un UPDATE parcial, esto es complejo.
        
        # Para mantenerlo simple y funcional con el nuevo esquema:
        # Extraemos los campos raiz
        flat_data = dto.model_dump(exclude={"personal", "medica", "deportiva", "performance"}, exclude_none=True)
        
        # Si se envia performance (JSON), lo pasamos directo
        if dto.performance:
             flat_data["performance"] = dto.performance
             
        # TODO: Implementar mapeo inverso completo si se requiere editar perfil desde la App.
        # Por ahora la App edita principalmente status y performance.
        
        # Actualizar
        updated = await self.repository.update(athlete_id, flat_data)
        await self.db.commit()
        
        logger.info(f"Atleta {athlete_id} actualizado")
        
        # Reutilizamos get_athlete para devolver el objeto completo y formateado
        return await self.get_athlete(athlete_id)

    async def update_status(self, athlete_id: str, dto: AthleteStatusUpdateDTO) -> AthleteDTO:
        """
        Actualiza solo el training_status de un atleta.
        
        Args:
            athlete_id: ID del atleta
            dto: DTO con el nuevo status
            
        Returns:
            AthleteDTO actualizado
            
        Raises:
            AthleteNotFoundException: Si el atleta no existe
        """
        success = await self.repository.update_status(athlete_id, dto.training_status)
        
        if not success:
            raise AthleteNotFoundException(athlete_id)
        
        await self.db.commit()
        
        logger.info(f"Training Status del atleta {athlete_id} cambiado a '{dto.training_status}'")
        
        return await self.get_athlete(athlete_id)

    async def create_athlete(self, dto: AthleteCreateDTO) -> AthleteDTO:
        """
        Crea un nuevo atleta.
        
        Args:
            dto: Datos del atleta a crear
            
        Returns:
            AthleteDTO creado
        """
        # Convertir DTO anidado a plano para crear
        # Mapeo basico de campos raiz
        athlete_data = dto.model_dump(exclude={"personal", "medica", "deportiva"}, mode='json')
        
        # Si vienen datos anidados, podriamos intentar colapsarlos, pero
        # la creacion desde App usualmente es basica.
        # Si se requiere crear perfil completo, necesitariamos el mapper inverso.
        
        athlete = await self.repository.create(athlete_data)
        await self.db.commit()
        
        return await self.get_athlete(athlete.id)

    async def seed_athletes(self, athletes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Carga masiva de atletas desde datos externos.
        
        Args:
            athletes_data: Lista de diccionarios con datos de atletas
            
        Returns:
            Diccionario con estadisticas del seed
        """
        count = await self.repository.seed_from_data(athletes_data)
        await self.db.commit()
        
        logger.info(f"Seed de atletas completado: {count} registros procesados")
        
        return {
            "processed": count,
            "message": f"Se procesaron {count} atletas correctamente"
        }

    async def get_status_counts(self) -> Dict[str, int]:
        """
        Obtiene el conteo de atletas por status.
        
        Returns:
            Diccionario con conteos por status
        """
        return await self.repository.get_status_counts()

    async def delete_athlete(self, athlete_id: str) -> bool:
        """
        Elimina un atleta.
        
        Args:
            athlete_id: ID del atleta a eliminar
            
        Returns:
            True si se elimino
            
        Raises:
            AthleteNotFoundException: Si el atleta no existe
        """
        success = await self.repository.delete(athlete_id)
        
        if not success:
            raise AthleteNotFoundException(athlete_id)
        
        await self.db.commit()
        
        logger.info(f"Atleta {athlete_id} eliminado")
        return True

