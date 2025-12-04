"""
Manejadores de eventos de inicio y cierre de la aplicacion.
"""
from typing import Callable
from fastapi import FastAPI
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.session import init_db, close_db
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.autogen.chat_manager import ChatManager
from app.infrastructure.mcp.mcp_server_manager import MCPServerManager
from app.shared.utils.audit_logger import AuditLogger


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
            
            # Configurar logging adicional
            logger.add(
                settings.LOG_FILE,
                rotation="500 MB",
                retention="10 days",
                level=settings.LOG_LEVEL
            )
            
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

