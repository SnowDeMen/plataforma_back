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
from datetime import datetime, timedelta, date
from app.core.config import settings
from app.shared.utils.date_utils import calculate_next_start_date

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

    async def automate_athlete_sync_and_generation(self, athlete_id: str, start_date: Optional[date] = None):
        """
        Ejecuta el flujo completo de automatización para un atleta.
        """
        athlete = await self.repository.get_by_id(athlete_id)
        if not athlete:
            logger.error(f"Atleta {athlete_id} no encontrado")
            return

        # Restringir a 'activo' y 'prueba'
        allowed_statuses = ["activo", "prueba"]
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

            # Usar start_date proporcionado o default (mañana)
            final_start_date = start_date or (datetime.now() + timedelta(days=1)).date()

            dto = PlanGenerationRequestDTO(
                athlete_id=athlete_id,
                athlete_name=athlete.name,
                athlete_info=athlete_info,
                weeks=settings.ATHLETE_TRAINING_GEN_WEEKS,
                start_date=final_start_date
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
        today = datetime.now().date()
        for athlete_id in new_record_ids:
            try:
                # 1. Verificar si el atleta tiene fecha de inicio futura
                athlete = await self.repository.get_by_id(athlete_id)
                if athlete and athlete.training_start_date and athlete.training_start_date > today:
                    logger.info(f"Atleta {athlete.name} tiene fecha de inicio futura ({athlete.training_start_date}). Marcando como 'Pendiente ingreso'.")
                    await self.repository.update(athlete_id, {"training_status": "Pendiente ingreso"})
                    await self.db.commit()
                    continue

                # 2. El flujo completo normal: Sync TP Profile -> Sync Historial -> Generación Plan
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
        Modificado para:
        1. Solo procesar "Por generar" o "En diagnóstico".
        2. Usar plan_end_date para optimizar (evitar TP scraping si no ha terminado el bloque).
        3. Calcular start_date considerando días de descanso (rest day awareness).
        """
        from sqlalchemy import select, func
        from app.infrastructure.database.models import AthleteModel
        from app.infrastructure.repositories.system_settings_repository import SystemSettingsRepository
        
        try:
            logger.info("Iniciando revisión de atletas para generación periódica...")
            
            # Obtener configuración de días de anticipación
            settings_repo = SystemSettingsRepository(self.db)
            days_in_advance = await settings_repo.get_value("days_in_advance_generation", 3)
            logger.info(f"Días de anticipación configurados: {days_in_advance}")
            
            # 1. Obtener atletas en estados elegibles: "Por generar" o "En diagnóstico"
            query = select(AthleteModel).where(
                AthleteModel.is_deleted == False
            ).where(
                func.lower(AthleteModel.client_status).in_(["activo", "prueba"])
            ).where(
                AthleteModel.training_status.in_(["Por generar", "En diagnóstico", "Plan activo", "Por revisar"])
            )
            
            result = await self.db.execute(query)
            athletes = result.scalars().all()
            
            if not athletes:
                logger.info("No hay atletas activos en estados elegibles para automatización.")
                return

            today = datetime.now().date()
            
            # 2. Filtrar atletas que ya tienen plan_end_date en el futuro (Optimización)
            athletes_needing_tp_check = []
            athletes_ready_with_local_date = []
            # Calcular fecha límite que justifica la generación de un nuevo plan
            threshold_date = today + timedelta(days=days_in_advance)
            
            for a in athletes:
                if a.plan_end_date and a.plan_end_date > threshold_date:
                    logger.debug(f"Omitiendo TP check para {a.name}: tiene plan activo hasta {a.plan_end_date} (fuera del umbral de {days_in_advance} días)")
                    continue
                
                # Si plan_end_date es hoy o pasado, ya podemos usarlo como base para el nuevo start_date
                # Evitando el scrape de TP si el dato local es confiable (opcional, pero optimiza)
                if a.plan_end_date and a.plan_end_date <= today:
                    # El nuevo plan empieza el día después de que terminó el anterior
                    baseline_date = a.plan_end_date + timedelta(days=1)
                    athletes_ready_with_local_date.append((a, baseline_date))
                else:
                    # No tenemos plan_end_date confiable, necesitamos preguntar a TP
                    athletes_needing_tp_check.append(a)

            # 3. Extraer fechas de TP solo para los que realmente lo necesitan
            tp_dates = {}
            if athletes_needing_tp_check:
                logger.info(f"Extrayendo fechas de TP para {len(athletes_needing_tp_check)} atletas...")
                def _scrape_all_dates():
                    session = None
                    try:
                        session = DriverManager.create_session("PeriodicTrainingSync")
                        session.auth_service.login_with_cookie()
                        return session.athlete_service.get_all_last_workout_dates()
                    except Exception as e:
                        logger.error(f"Error en extraccion masiva de fechas TP: {e}")
                        return {}
                    finally:
                        if session:
                            session.close()

                tp_dates = await run_selenium(_scrape_all_dates)
            
            # 4. Consolidar lista final a procesar
            final_processing_queue = [] # List of (athlete, start_date)
            
            # Agregar los que ya tenían fecha local
            for a, base_date in athletes_ready_with_local_date:
                start_date = calculate_next_start_date(base_date, a.preferred_rest_day)
                final_processing_queue.append((a, start_date))
            
            # Procesar los scrapeados de TP
            for a in athletes_needing_tp_check:
                search_name = (a.tp_name or a.name).strip().lower()
                scraped_date = None
                
                if search_name in tp_dates:
                    try:
                        d_str = tp_dates[search_name]
                        try:
                            scraped_date = datetime.strptime(d_str, "%m/%d/%y").date()
                        except ValueError:
                            scraped_date = datetime.strptime(d_str, "%m/%d/%Y").date()
                    except (ValueError, TypeError):
                        pass

                if scraped_date:
                    if scraped_date <= today:
                        # El plan empieza el día después del último workout
                        base_date = scraped_date + timedelta(days=1)
                        # Pero si el día después es pasado (ej: dejó de entrenar hace 1 mes), 
                        # empezamos mañana como mínimo
                        if base_date <= today:
                            base_date = today + timedelta(days=1)
                            
                        start_date = calculate_next_start_date(base_date, a.preferred_rest_day)
                        final_processing_queue.append((a, start_date))
                    else:
                        logger.debug(f"{a.name}: TP dice que tiene plan hasta {scraped_date}. Ignorando.")
                else:
                    # Ultimo recurso: fallback a threshold de dias desde ultima generacion
                    # (Esto maneja atletas nuevos que ni siquiera salen en el sidebar)
                    threshold_date = datetime.now() - timedelta(days=threshold_days)
                    
                    last_gen = a.last_training_generation_at
                    if last_gen and last_gen.tzinfo is not None:
                        last_gen = last_gen.replace(tzinfo=None)
                        
                    if not last_gen or last_gen <= threshold_date:
                        # Empezar mañana y aplicar bumping
                        start_date = calculate_next_start_date(today + timedelta(days=1), a.preferred_rest_day)
                        final_processing_queue.append((a, start_date))

            if not final_processing_queue:
                logger.info("Ningún atleta requiere generación de plan tras aplicar filtros y optimizaciones.")
                return

            logger.info(f"Se procesarán {len(final_processing_queue)} atletas.")
            
            for athlete, start_date in final_processing_queue:
                try:
                    logger.info(f"Gatillando automatización para {athlete.name}. Inicio planeado: {start_date}")
                    await self.automate_athlete_sync_and_generation(athlete.id, start_date=start_date)
                except Exception as ex:
                    logger.error(f"Error procesando automatización periódica para {athlete.name}: {ex}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error en generate_periodic_trainings: {e}")

