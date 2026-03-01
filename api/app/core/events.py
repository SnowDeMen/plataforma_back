"""
Manejadores de eventos de inicio y cierre de la aplicacion.
"""
import asyncio
from typing import Callable
from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.session import init_db, close_db
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.autogen.chat_manager import ChatManager
from app.shared.utils.audit_logger import AuditLogger
from app.infrastructure.external.airtable_sync.sync_service import build_from_env
from app.infrastructure.external.airtable_sync.table_mappings import get_table_sync_config
from app.infrastructure.database.session import init_db, close_db, AsyncSessionLocal
from app.infrastructure.database.models import AthleteModel
from app.application.use_cases.sync_use_cases import AthleteAutomationUseCase
from app.application.use_cases.notification_use_cases import NotificationUseCases
from app.application.use_cases.admin_use_cases import AdminUseCases
from app.application.use_cases.athlete_use_cases import AthleteUseCases
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.infrastructure.repositories.system_settings_repository import SystemSettingsRepository
from sqlalchemy import select, or_, func
from datetime import timedelta, datetime


def startup_handler(app: FastAPI) -> Callable:
    """
    Manejador de eventos de inicio de la aplicacion.
    
    Args:
        app: Instancia de FastAPI
        
    Returns:
        Callable: Funcion asincrona de inicio
    """
    async def startup() -> None:
        """Inicializa recursos al inicio de la aplicacion."""
        try:
            logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")
            logger.info(f"Entorno: {settings.ENVIRONMENT}")
            
            # Validar configuracion critica
            _validate_config()
            
            # Inicializar base de datos (crea tablas si no existen)
            await init_db()
            logger.info("Base de datos inicializada")
            
            # Inicializar sistema de auditoria
            AuditLogger.initialize()
            logger.info("Sistema de auditoria inicializado")
            
            # Registrar alertas de entrenamiento por defecto
            from app.application.services.alert_evaluators import register_default_alerts
            register_default_alerts()
            logger.info("Sistema de alertas de entrenamiento inicializado")
            
            # Configurar logging adicional
            logger.add(
                settings.LOG_FILE,
                rotation="500 MB",
                retention="10 days",
                level=settings.LOG_LEVEL
            )
            
            # Inicializar y programar tareas (Sync Airtable, Notificaciones, etc)
            await _setup_scheduler(app)
            
            logger.success("Aplicacion iniciada correctamente")
            
            # Mostrar URLs disponibles
            _print_available_urls()
            
        except Exception as e:
            logger.error(f"Error durante startup: {e}")
            logger.exception("Detalle del error:")
            raise
    
    return startup


def _validate_config() -> None:
    """Valida que la configuracion critica este presente."""
    warnings = []
    
    # Verificar OPENAI_API_KEY
    if not settings.OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY no configurada - el chat no funcionara")
    
    # Mostrar advertencias
    for warning in warnings:
        logger.warning(f"CONFIG: {warning}")


def _print_available_urls() -> None:
    """Imprime las URLs disponibles de la aplicacion."""
    # Determinar la URL base de acceso
    if settings.HOST == "0.0.0.0":
        access_host = "localhost"
    else:
        access_host = settings.HOST
    
    base_url = f"http://{access_host}:{settings.PORT}"
    
    # Mostrar las URLs disponibles
    logger.opt(colors=True).info("<bold><green>" + "=" * 80 + "</green></bold>")
    logger.opt(colors=True).info("<bold><green>URLS DISPONIBLES:</green></bold>")
    logger.opt(colors=True).info("<bold><green>" + "=" * 80 + "</green></bold>")
    logger.opt(colors=True).info(f"<cyan>  Swagger UI:  {base_url}/docs</cyan>")
    logger.opt(colors=True).info(f"<cyan>  ReDoc:       {base_url}/redoc</cyan>")
    logger.opt(colors=True).info(f"<cyan>  OpenAPI:     {base_url}/openapi.json</cyan>")
    logger.opt(colors=True).info(f"<cyan>  Health:      {base_url}/health</cyan>")
    logger.opt(colors=True).info("<bold><green>" + "=" * 80 + "</green></bold>")


async def _setup_scheduler(app: FastAPI) -> None:
    """Configura y arranca el programador de tareas."""
    scheduler = AsyncIOScheduler()
    
    async with AsyncSessionLocal() as db:
        # 1. Poblar configuraciones por defecto
        admin_use_cases = AdminUseCases(db)
        await admin_use_cases.seed_default_settings()
        
        # 2. Obtener intervalo de notificaciones de Telegram (desde DB o config)
        settings_repo = SystemSettingsRepository(db)
        tg_interval = await settings_repo.get_value("telegram_notification_interval_hours", 24.0)

    # Job: Sync Airtable
    if all([settings.AIRTABLE_TOKEN, settings.AIRTABLE_BASE_ID, settings.AIRTABLE_TABLE_NAME]):
        scheduler.add_job(
            _run_sync_task,
            trigger=IntervalTrigger(hours=settings.AIRTABLE_SYNC_INTERVAL_HOURS),
            id="airtable_sync",
            replace_existing=True
        )
        if settings.RUN_STARTUP_TASKS:
            scheduler.add_job(_run_sync_task, id="airtable_sync_initial")
    else:
        logger.warning("Configuracion de Airtable incompleta - el sync automatico no se iniciara")

    # Job: Entrenamiento Periódico
    if settings.RUN_STARTUP_TASKS:
        scheduler.add_job(_run_periodic_training_generation_task, id="periodic_training_generation_initial")
        
    scheduler.add_job(
        _run_periodic_training_generation_task,
        trigger=IntervalTrigger(hours=settings.ATHLETE_TRAINING_GEN_INTERVAL_HOURS),
        id="periodic_training_generation",
        replace_existing=True
    )
    
    # Job: Notificaciones Telegram (Atletas Pendientes)
    scheduler.add_job(
        _run_telegram_notification_task,
        trigger=IntervalTrigger(hours=tg_interval),
        id="telegram_notification",
        replace_existing=True
    )
    # Ejecutar una vez al inicio también si está habilitado
    if settings.RUN_STARTUP_TASKS:
        scheduler.add_job(_run_telegram_notification_task, id="telegram_notification_initial")
        
    # Job: Limpieza de atletas inactivos (Baja > 3 meses)
    scheduler.add_job(
        _run_inactive_athlete_cleanup_task,
        trigger=IntervalTrigger(hours=24),
        id="inactive_athlete_cleanup",
        replace_existing=True
    )
    if settings.RUN_STARTUP_TASKS:
        scheduler.add_job(_run_inactive_athlete_cleanup_task, id="inactive_athlete_cleanup_initial")
        
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(f"Programador de tareas iniciado (Sync, Entrenamientos, Telegram)")


async def _run_telegram_notification_task() -> None:
    """Ejecuta la notificación de Telegram para atletas pendientes."""
    try:
        logger.info("Ejecutando tarea de notificación de Telegram...")
        async with AsyncSessionLocal() as db:
            notification = NotificationUseCases(db)
            await notification.notify_pending_review_athletes()
    except Exception as e:
        logger.error(f"Error en tarea de notificación de Telegram: {e}")

async def _run_inactive_athlete_cleanup_task() -> None:
    """Ejecuta la logica de limpieza de atletas inactivos (Baja > 3 meses)."""
    try:
        logger.info("Iniciando tarea de limpieza de atletas inactivos...")
        async with AsyncSessionLocal() as db:
            use_case = AthleteUseCases(db)
            result = await use_case.process_inactive_athletes()
            logger.info(f"Limpieza de inactivos completada: {result}")
    except Exception as e:
        logger.error(f"Error en tarea de limpieza de inactivos: {e}")
        logger.exception(e)


async def _run_sync_task() -> None:
    """Ejecuta la logica de sincronizacion de Airtable y Training Peaks."""
    try:
        logger.info("Iniciando Airtable -> Postgres sync (tarea programada)...")
        # Reusamos la logica del script CLI
        service, pg_repo, _ = build_from_env(pg_dsn_env="DATABASE_URL")
        ç
        config = get_table_sync_config(
            airtable_table_name=settings.AIRTABLE_TABLE_NAME,
            airtable_last_modified_field=settings.AIRTABLE_LAST_MOD_FIELD,
            target_schema=settings.AIRTABLE_PG_SCHEMA,
            target_table=settings.AIRTABLE_PG_TABLE or None,
        )
        
        # Generar lock key determinista
        raw = ("airtable_sync:" + config.airtable_table_name).encode("utf-8")
        lock_key = int(sum(raw) % (2**31 - 1))
        
        # Ejecutar el sync síncrono en un thread para no bloquear el event loop de FastAPI
        result = await asyncio.to_thread(service.run_once, config=config, pg_lock_key=lock_key)
        logger.info(f"Sync finalizado: upserted_rows={result.upserted_rows}, new_inserts={len(result.new_record_ids)}")
        
        # Orquestar automatizaciones para atletas nuevos y reintentos TP
        async with AsyncSessionLocal() as db:
            automation = AthleteAutomationUseCase(db)
            
            # 1. Automatización inicial para atletas nuevos
            await automation.process_new_athletes(result.new_record_ids)
            
            # 2. Reintentar sincronización de TP para atletas activos sin nombres
            exclude_ids = result.new_record_ids if result.new_record_ids else []
            await automation.sync_missing_tp_names(exclude_ids=exclude_ids)
        
    except Exception as e:
        logger.error(f"Error en tarea de sync programada: {e}")
        logger.exception(e)


async def _run_periodic_training_generation_task() -> None:
    """
    Tarea periódica para generar automáticamente entrenamientos para atletas.
    Busca atletas que no han tenido generación reciente y dispara el flujo.
    """
    try:
        logger.info("Iniciando revisión de atletas para generación periódica de entrenamientos...")
        
        async with AsyncSessionLocal() as db:
            automation = AthleteAutomationUseCase(db)
            await automation.generate_periodic_trainings(
                threshold_days=settings.ATHLETE_TRAINING_GEN_THRESHOLD_DAYS
            )

    except Exception as e:
        logger.error(f"Error en tarea de generación periódica: {e}")
        logger.exception(e)


def shutdown_handler(app: FastAPI) -> Callable:
    """
    Manejador de eventos de cierre de la aplicacion.
    
    Args:
        app: Instancia de FastAPI
        
    Returns:
        Callable: Funcion asincrona de cierre
    """
    async def shutdown() -> None:
        """Libera recursos al cerrar la aplicacion."""
        logger.info("Cerrando aplicacion...")
        
        # Detener programador de tareas
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.shutdown()
            logger.info("Programador de tareas detenido")
        
        # Cerrar todas las sesiones de driver de Selenium
        closed_sessions = DriverManager.close_all_sessions()
        logger.info(f"Sesiones de driver cerradas: {closed_sessions}")
        
        # Limpiar todos los agentes de chat en memoria
        closed_agents = ChatManager.clear_all()
        logger.info(f"Agentes de chat cerrados: {closed_agents}")
        
        # Cerrar conexiones de base de datos
        await close_db()
        logger.info("Conexiones de base de datos cerradas")
        
        logger.success("Aplicacion cerrada correctamente")
    
    return shutdown

