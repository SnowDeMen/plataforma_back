"""
Casos de uso para sincronización externa (TrainingPeaks, Airtable).
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.services.athlete_service import AthleteService
from app.infrastructure.driver.selenium_executor import run_selenium
from app.infrastructure.external.airtable_sync.airtable_client import AirtableClient, AirtableCredentials
from app.application.use_cases.plan_use_cases import PlanUseCases
from app.application.dto.plan_dto import PlanGenerationRequestDTO, AthleteInfoDTO
from datetime import datetime, timedelta
from app.core.config import settings

from app.application.use_cases.tp_sync_use_cases import TPSyncUseCases

class AthleteAutomationUseCase:
    """
    Orquestador reutilizable para la automatización de tareas de atletas.
    Encapsula el flujo: Sync Perfil -> Generación de Plan.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = AthleteRepository(db)
        self.tp_sync = TPSyncUseCases()
        self.plan_use_cases = PlanUseCases(db)

    async def automate_athlete_sync_and_generation(self, athlete_id: str):
        """
        Ejecuta el flujo completo de automatización para un atleta.
        """
        athlete = await self.repository.get_by_id(athlete_id)
        if not athlete:
            logger.error(f"Atleta {athlete_id} no encontrado")
            return

        logger.info(f"Iniciando automatización completa para: {athlete.name}")

        # 1. Sincronizar Username y tp_name si es necesario
        tp_username = athlete.tp_username
        if not tp_username:
            logger.info(f"Descubriendo username TP para {athlete.name}...")
            # Usar TPSyncUseCases para descubrir y sincronizar
            # Pasamos username=None para que intente descubrirlo por nombre
            result = await self.tp_sync.execute_sync_process(username=None, athlete_id=athlete_id)
            if result.get("success") and result.get("username"):
                tp_username = result["username"]
        
        if not tp_username:
            logger.warning(f"No se puede automatizar {athlete.name} sin username de TrainingPeaks")
            return

        # 2. Generar Plan de Entrenamiento
        logger.info(f"Generando plan de entrenamiento para {athlete.name}...")
        try:
            # Construir AthleteInfoDTO a partir del modelo
            athlete_info = AthleteInfoDTO(
                age=athlete.age,
                discipline=athlete.discipline or athlete.athlete_type,
                level=athlete.level,
                goal=athlete.goal or athlete.main_event or athlete.short_term_goal,
                experience=athlete.experience,
                personal={
                    "nombreCompleto": athlete.full_name,
                    "genero": athlete.gender,
                    "tipoAtleta": athlete.athlete_type,
                    "sesionesSemanales": athlete.training_frequency_weekly,
                    "horasSemanales": athlete.training_hours_weekly,
                },
                medica={
                    "enfermedades": athlete.diseases_conditions,
                    "lesionAguda": athlete.acute_injury_disease,
                    "tipoLesion": athlete.acute_injury_type,
                    "dieta": athlete.diet_type
                },
                deportiva={
                    "tiempoPracticando": athlete.running_experience_time,
                    "eventoObjetivo": athlete.main_event,
                },
                performance=athlete.performance if athlete.performance else {}
            )

            dto = PlanGenerationRequestDTO(
                athlete_id=athlete_id,
                athlete_name=athlete.name,
                athlete_info=athlete_info,
                weeks=settings.ATHLETE_TRAINING_GEN_WEEKS,
                start_date=(datetime.now() + timedelta(days=1)).date()
            )
            await self.plan_use_cases.create_and_generate(dto)
            
            # 4. Actualizar status y timestamp
            await self.repository.update(athlete_id, {
                "status": "Por Revisar",
                "last_training_generation_at": datetime.now()
            })
            await self.db.commit()
            logger.success(f"Automatización completada exitosamente para {athlete.name}")
        except Exception as e:
            logger.error(f"Error generando plan para {athlete.name}: {e}")
            await self.db.rollback()
