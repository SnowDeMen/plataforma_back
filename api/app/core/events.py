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
from app.infrastructure.mcp.mcp_server_manager import MCPServerManager
from app.shared.utils.audit_logger import AuditLogger
from app.infrastructure.external.airtable_sync.sync_service import build_from_env
from app.infrastructure.external.airtable_sync.table_mappings import get_table_sync_config
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


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
            
            # Inicializar y programar sync de Airtable
            await _setup_airtable_sync(app)
            
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


async def _setup_airtable_sync(app: FastAPI) -> None:
    """Configura y arranca el programador de sync de Airtable."""
    if not all([settings.AIRTABLE_TOKEN, settings.AIRTABLE_BASE_ID, settings.AIRTABLE_TABLE_NAME]):
        logger.warning("Configuracion de Airtable incompleta - el sync automatico no se iniciara")
        return

    scheduler = AsyncIOScheduler()
    
    # Programar la tarea periódica
    scheduler.add_job(
        _run_sync_task,
        trigger=IntervalTrigger(hours=settings.AIRTABLE_SYNC_INTERVAL_HOURS),
        id="airtable_sync",
        replace_existing=True
    )
    
    # Para ejecutar una vez al inicio
    scheduler.add_job(_run_sync_task, id="airtable_sync_initial")
    
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(f"Programador de Airtable sync iniciado (intervalo: {settings.AIRTABLE_SYNC_INTERVAL_HOURS}h)")


async def _run_sync_task() -> None:
    """Ejecuta la logica de sincronizacion de Airtable."""
    try:
        logger.info("Iniciando Airtable -> Postgres sync (tarea programada)...")
        # Reusamos la logica del script CLI
        service, pg_repo, _ = build_from_env(pg_dsn_env="DATABASE_URL")
        
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
        logger.info(f"Sync finalizado: upserted_rows={result.upserted_rows}")
        
    except Exception as e:
        logger.error(f"Error en tarea de sync programada: {e}")
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
        
        # Detener servidor MCP
        MCPServerManager.stop()
        logger.info("Servidor MCP detenido")
        
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

