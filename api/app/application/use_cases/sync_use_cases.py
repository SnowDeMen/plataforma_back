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

        # Restringir a 'activo'
        allowed_statuses = ["activo"]
        if not athlete.client_status or athlete.client_status.lower() not in allowed_statuses:
            logger.info(f"Omitiendo automatización para {athlete.name}: status '{athlete.client_status}' no es elegible.")
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
            
            # 4. Actualizar training_status y timestamp
            await self.repository.update(athlete_id, {
                "training_status": "Por revisar",
                "last_training_generation_at": datetime.now()
            })
            await self.db.commit()
            logger.success(f"Automatización completada exitosamente para {athlete.name}")
        except Exception as e:
            logger.error(f"Error generando plan para {athlete.name}: {e}")
            await self.db.rollback()

    async def process_new_athletes(self, new_record_ids: list[str]) -> None:
        """
        Orquesta la automatización inicial para atletas recién insertados.
        """
        if not new_record_ids:
            return
            
        logger.info(f"Disparando automatización inicial para {len(new_record_ids)} atletas nuevos")
        for athlete_id in new_record_ids:
            try:
                # El flujo completo: Sync TP Profile -> Sync Historial -> Generación Plan
                await self.automate_athlete_sync_and_generation(athlete_id)
            except Exception as e:
                logger.error(f"Error procesando nuevo atleta {athlete_id}: {e}")

    async def sync_missing_tp_names(self, exclude_ids: Optional[list[str]] = None) -> None:
        """
        Busca e intenta sincronizar los atletas activos que aún no tienen tp_name.
        """
        from sqlalchemy import select, func, or_
        from app.infrastructure.database.models import AthleteModel
        
        exclude_ids = exclude_ids or []
        
        try:
            query_missing = select(AthleteModel).where(
                func.lower(AthleteModel.client_status) == "activo",
                or_(AthleteModel.tp_name.is_(None), AthleteModel.tp_name == "")
            )
            result_missing = await self.db.execute(query_missing)
            missing_athletes = result_missing.scalars().all()

            if missing_athletes:
                # Filtrar aquellos que acaban de ser procesados (ej. como nuevos)
                missing_to_process = [
                    a for a in missing_athletes 
                    if a.id not in exclude_ids
                ]
                
                if missing_to_process:
                    logger.info(f"Reintentando sincronización de TrainingPeaks para {len(missing_to_process)} atletas activos sin nombre (TP).")
                    for athlete in missing_to_process:
                        logger.info(f"Reintentando TP Sync para atleta ya existente: {athlete.name}")
                        try:
                            await self.tp_sync.execute_sync_process(username=athlete.tp_username, athlete_id=athlete.id)
                        except Exception as ex:
                            logger.error(f"Error reintentando TP sync para {athlete.name}: {ex}")
        except Exception as e:
            logger.error(f"Error en sync_missing_tp_names: {e}")

    async def generate_periodic_trainings(self, threshold_days: int) -> None:
        """
        Busca atletas que no han tenido generación reciente y dispara el flujo.
        """
        from sqlalchemy import select, func, or_
        from app.infrastructure.database.models import AthleteModel
        
        try:
            logger.info("Iniciando revisión de atletas para generación periódica de entrenamientos...")
            threshold_date = datetime.now() - timedelta(days=threshold_days)
            
            query = select(AthleteModel).where(
                or_(
                    AthleteModel.last_training_generation_at == None,
                    AthleteModel.last_training_generation_at <= threshold_date
                )
            ).where(
                AthleteModel.is_deleted == False
            ).where(
                func.lower(AthleteModel.client_status).in_(["activo", "prueba"])
            )
            
            result = await self.db.execute(query)
            athletes = result.scalars().all()
            
            if not athletes:
                logger.info("No hay atletas que requieran generación periódica en este momento.")
                return

            logger.info(f"Se encontraron {len(athletes)} atletas para revisión de automatización.")
            
            for athlete in athletes:
                try:
                    await self.automate_athlete_sync_and_generation(athlete.id)
                except Exception as ex:
                    logger.error(f"Error procesando automatización periódica para {athlete.name}: {ex}")
                    continue
        except Exception as e:
            logger.error(f"Error en generate_periodic_trainings: {e}")
