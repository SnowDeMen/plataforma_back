"""
Casos de uso relacionados con atletas.
Contiene la logica de negocio para consultar informacion de atletas.
"""
from typing import List, Optional
from loguru import logger

from app.application.dto.athlete_dto import AthleteDTO
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.infrastructure.database.models import AthleteModel
from app.shared.exceptions.domain import EntityNotFoundException


class AthleteUseCases:
    """
    Casos de uso para gestion de informacion de atletas.
    """
    
    def __init__(self, repository: AthleteRepository):
        self.repository = repository
        
    async def get_all_athletes(self) -> List[AthleteDTO]:
        """
        Obtiene todos los atletas disponibles.
        
        Returns:
            List[AthleteDTO]: Lista de atletas
        """
        athletes = await self.repository.get_all()
        return [self._map_model_to_dto(athlete) for athlete in athletes]
        
    async def get_athlete(self, athlete_id: str) -> AthleteDTO:
        """
        Obtiene un atleta por su ID.
        
        Args:
            athlete_id: ID del atleta
            
        Returns:
            AthleteDTO: Informacion del atleta
            
        Raises:
            EntityNotFoundException: Si el atleta no existe
        """
        athlete = await self.repository.get_by_id(athlete_id)
        
        if not athlete:
            raise EntityNotFoundException("Athlete", athlete_id)
            
        return self._map_model_to_dto(athlete)

    def _map_model_to_dto(self, row: AthleteModel) -> AthleteDTO:
        """
        Convierte un AthleteModel plano a la estructura anidada de AthleteDTO.
        Logica movida desde el endpoint.
        """
        # Helper cleanup
        def clean_pg_array(val: Optional[str]) -> List[str]:
            if not val:
                return []
            cleaned = val.replace("{", "").replace("}", "").replace('"', "")
            return [x.strip() for x in cleaned.split(",")]

        # Construcción de secciones anidadas
        personal = {
            "nombreCompleto": row.full_name,
            "genero": row.gender,
            "pesoActual": row.current_weight, 
            "tipoAtleta": row.athlete_type,
            "sesionesSemanales": row.training_frequency_weekly,
            "horasSemanales": row.training_hours_weekly,
            "horarioPreferido": row.preferred_schedule,
            "diaDescanso": row.preferred_rest_day,
            "city": row.city,
            "state": row.state,
        }

        medica = {
            "enfermedades": row.diseases_conditions,
            "lesiones": row.acute_injury_disease,
            "medicamentos": row.medications,
            "suplementos": row.supplements,
            "horasSueno": row.daily_sleep_hours,
            "calidadSueno": row.sleep_quality,
            "dieta": row.diet_type,
            "dietaDescripcion": row.diet_description,
        }

        medidores_list = clean_pg_array(row.sensors_owned)
        discipline_list = clean_pg_array(row.disciplines_count)
        discipline_str = ", ".join(discipline_list)

        deportiva = {
            "tiempoPracticando": row.running_experience_time,
            "records": {
                "dist5k": row.best_time_5k,
                "dist10k": row.best_time_10k,
                "dist21k": row.best_time_21k,
                "maraton": row.marathon_time,
                "triatlon": row.triathlon_time,
                "distanciaMaxima": row.longest_run_distance,
            },
            "medidores": medidores_list,
            "equipoDisponible": f"Pool: {row.has_pool_access}, Trainer: {row.has_smart_trainer}",
            "eventoObjetivo": row.main_event,
            "metasAnuales": row.annual_goals,
            "previousSports": row.previous_sports,
        }

        return AthleteDTO(
            id=row.airtable_record_id,
            airtable_id=row.airtable_record_id,
            name=row.full_name or "Sin Nombre",
            status=row.status or "Por generar",
            discipline=discipline_str,
            level=row.athlete_type,
            goal=row.main_event,
            age=None, 
            experience=row.running_experience_time,
            personal=personal,
            medica=medica,
            deportiva=deportiva,
            performance=None 
        )
