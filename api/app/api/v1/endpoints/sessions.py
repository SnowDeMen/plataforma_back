"""
Endpoints para operaciones con sesiones de entrenamiento.
Maneja la creacion, consulta y cierre de sesiones con drivers de Selenium.
Incluye inicializacion automatica del MCP y agente de chat.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.application.use_cases.session_use_cases import SessionUseCases
from app.application.dto.session_dto import SessionStartDTO, SessionResponseDTO, TPSyncResultDTO
from app.api.v1.dependencies.use_case_deps import get_session_use_cases
from app.infrastructure.database.session import get_db
from app.infrastructure.repositories.chat_repository import ChatRepository
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.infrastructure.autogen.chat_manager import ChatManager
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.selenium_executor import run_selenium
from app.infrastructure.mcp.mcp_server_manager import MCPServerManager
from app.shared.utils.audit_logger import AuditLogger


router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post(
    "/",
    response_model=SessionResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar una nueva sesion de entrenamiento"
)
async def start_session(
    dto: SessionStartDTO,
    use_cases: SessionUseCases = Depends(get_session_use_cases),
    db: AsyncSession = Depends(get_db)
) -> SessionResponseDTO:
    """
    Inicia una nueva sesion de entrenamiento para un atleta.
    
    El flujo completo incluye:
    1. Validacion del atleta
    2. Inicializacion del driver de Selenium (login, seleccion atleta, etc.)
    3. Inicializacion del MCP con el driver para herramientas de TrainingPeaks
    4. Creacion del agente de chat asociado a la sesion
    5. Persistencia de la sesion de chat en base de datos
    
    Args:
        dto: Datos de inicio con el nombre del atleta
        use_cases: Casos de uso de sesiones (inyectado)
        db: Sesion de base de datos (inyectado)
        
    Returns:
        SessionResponseDTO: Informacion de la sesion iniciada con MCP y chat activos
        
    Raises:
        400: Si el atleta no es valido
    """
    # 1. Iniciar sesion de entrenamiento (driver)
    session_response = await use_cases.start_session(dto)
    
    # Crear logger de sesion para auditoria
    AuditLogger.get_session_logger(
        session_id=session_response.session_id,
        athlete_name=session_response.athlete_name
    )
    
    # Log de la request y evento de inicio
    AuditLogger.log_request(
        session_id=session_response.session_id,
        method="POST",
        path="/api/v1/sessions/",
        body={"athlete_name": dto.athlete_name}
    )
    
    AuditLogger.log_event(
        session_id=session_response.session_id,
        event="SESSION_CREATED",
        details={
            "athlete_name": session_response.athlete_name,
            "driver_active": session_response.driver_active
        }
    )
    
    # 2. Obtener la sesion del driver para inicializar el servidor MCP
    driver_session = DriverManager.get_session(session_response.session_id)
    
    # 3. Inicializar servidor MCP con el driver de la sesion
    # El servidor MCP se ejecuta en el mismo proceso con el driver inyectado
    mcp_initialized = False
    if driver_session:
        mcp_initialized = MCPServerManager.start(
            driver=driver_session.driver,
            wait=driver_session.wait,
            session_id=session_response.session_id,
            run_server=False  # Las herramientas se llaman directamente via MCPToolsAdapter
        )
        
        # Log de la inicializacion del servidor MCP
        AuditLogger.log_mcp_call(
            session_id=session_response.session_id,
            action="MCP_SERVER_START",
            details={
                "driver_available": True,
                "tools_available": MCPServerManager.get_available_tools()
            },
            success=mcp_initialized
        )
        
        if mcp_initialized:
            logger.info(
                f"Servidor MCP iniciado para sesion {session_response.session_id}. "
                f"Herramientas disponibles: {len(MCPServerManager.get_available_tools())}"
            )
        else:
            logger.warning(
                f"Servidor MCP no se pudo iniciar para sesion {session_response.session_id}"
            )
    
    # 4. Inicializar agente de chat para esta sesion
    chat_repo = ChatRepository(db)
    
    # Crear registro de chat en base de datos
    await chat_repo.create(
        session_id=session_response.session_id,
        athlete_name=session_response.athlete_name,
        athlete_id=session_response.athlete_id,
        system_message=None,  # Usara el default del ChatManager
        agent_config={"mcp_enabled": mcp_initialized}
    )
    
    # 5. Crear agente en memoria con contexto del atleta
    ChatManager.create_agent(
        session_id=session_response.session_id,
        athlete_name=session_response.athlete_name,
        athlete_info=dto.athlete_info
    )
    
    # Log del agente creado
    AuditLogger.log_event(
        session_id=session_response.session_id,
        event="CHAT_AGENT_CREATED",
        details={"mcp_enabled": mcp_initialized}
    )
    
    # Construir mensaje de respuesta
    mcp_status = "MCP activo" if mcp_initialized else "MCP no disponible"
    session_response.message = (
        f"Sesion iniciada para {dto.athlete_name}. "
        f"{mcp_status}. "
        f"Chat: /api/v1/sessions/{session_response.session_id}/chat/"
    )
    
    return session_response


@router.get(
    "/{session_id}",
    response_model=SessionResponseDTO,
    summary="Obtener estado de una sesion"
)
def get_session_status(
    session_id: str,
    use_cases: SessionUseCases = Depends(get_session_use_cases)
) -> SessionResponseDTO:
    """
    Obtiene el estado actual de una sesion de entrenamiento.
    
    Args:
        session_id: ID de la sesion a consultar
        use_cases: Casos de uso de sesiones (inyectado)
        
    Returns:
        SessionResponseDTO: Estado actual de la sesion
    """
    return use_cases.get_session_status(session_id)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar una sesion"
)
async def close_session(
    session_id: str,
    use_cases: SessionUseCases = Depends(get_session_use_cases),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Cierra una sesion y libera sus recursos.
    
    Incluye:
    - Limpieza del MCP si esta conectado a esta sesion
    - Cierre del ChromeDriver
    - Desactivacion de la sesion de chat
    - Eliminacion del agente de memoria
    
    Args:
        session_id: ID de la sesion a cerrar
        use_cases: Casos de uso de sesiones (inyectado)
        db: Sesion de base de datos (inyectado)
    """
    # Log de la request
    AuditLogger.log_request(
        session_id=session_id,
        method="DELETE",
        path=f"/api/v1/sessions/{session_id}"
    )
    
    # Log del evento de cierre
    AuditLogger.log_event(
        session_id=session_id,
        event="SESSION_CLOSING",
        details={"reason": "user_request"}
    )
    
    # Detener servidor MCP si esta conectado a esta sesion
    current_mcp_session = MCPServerManager.get_current_session_id()
    mcp_stopped = False
    if current_mcp_session == session_id:
        mcp_stopped = MCPServerManager.stop()
    
    AuditLogger.log_mcp_call(
        session_id=session_id,
        action="MCP_SERVER_STOP",
        success=mcp_stopped
    )
    
    # Cerrar driver de Selenium
    use_cases.close_session(session_id)
    
    # Desactivar sesion de chat en BD
    chat_repo = ChatRepository(db)
    await chat_repo.deactivate(session_id)
    
    # Eliminar agente de memoria
    ChatManager.remove_agent(session_id)
    
    # Cerrar el logger de sesion
    AuditLogger.close_session(session_id)


@router.get(
    "/{session_id}/mcp-status",
    summary="Obtener estado del servidor MCP"
)
def get_mcp_status(session_id: str) -> dict:
    """
    Obtiene el estado del servidor MCP para una sesion.
    
    Verifica si el servidor MCP esta inicializado y las herramientas disponibles.
    
    Args:
        session_id: ID de la sesion
        
    Returns:
        Dict con el estado del servidor MCP
    """
    mcp_status = MCPServerManager.get_status()
    
    # Verificar si esta sesion es la conectada al servidor MCP
    is_current_session = mcp_status.get("session_id") == session_id
    
    return {
        "session_id": session_id,
        "mcp_connected_to_session": is_current_session,
        "mcp_initialized": mcp_status.get("initialized", False),
        "mcp_server_running": mcp_status.get("server_running", False),
        "tools_available": mcp_status.get("tools_count", 0),
        "mcp_path_exists": mcp_status.get("mcp_path_exists", False)
    }

@router.post(
    "/{session_id}/restart",
    response_model=SessionResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Reiniciar driver de sesion"
)
async def restart_session(
    session_id: str,
    use_cases: SessionUseCases = Depends(get_session_use_cases),
    db: AsyncSession = Depends(get_db)
) -> SessionResponseDTO:
    """
    Reinicia el driver de Selenium para una sesion existente.
    
    Tambien reinicializa el servidor MCP y el agente si es necesario.
    
    Args:
        session_id: ID de la sesion a reiniciar
        use_cases: Casos de uso de sesiones (inyectado)
        db: Sesion de base de datos
        
    Returns:
        SessionResponseDTO: Informacion actualizada de la sesion
    """
    # 1. Reiniciar driver via use cases
    session_response = await use_cases.restart_session(session_id)
    
    # 2. Log del evento
    AuditLogger.log_event(
        session_id=session_id,
        event="SESSION_RESTARTED",
        details={"driver_active": True}
    )
    
    # 3. Inicializar servidor MCP
    driver_session = DriverManager.get_session(session_id)
    mcp_initialized = False
    
    if driver_session:
        # Detener servidor anterior si existia
        if MCPServerManager.get_current_session_id() == session_id:
            MCPServerManager.stop()
            
        # Iniciar nuevo servidor MCP
        mcp_initialized = MCPServerManager.start(
            driver=driver_session.driver,
            wait=driver_session.wait,
            session_id=session_id,
            run_server=False
        )
        
        if mcp_initialized:
            logger.info(f"Servidor MCP reinicializado para sesion {session_id}")
            AuditLogger.log_mcp_call(
                session_id=session_id,
                action="MCP_SERVER_RESTART",
                details={"tools_available": MCPServerManager.get_available_tools()},
                success=True
            )
    
    # 4. Asegurar que el agente este listo (recargar si es necesario)
    # ChatManager.get_agent(session_id) validara o recreara el agente si no existe
    
    session_response.message = f"Sesion reiniciada correctamente. MCP: {'Activo' if mcp_initialized else 'Inactivo'}"
    
    return session_response


@router.post(
    "/sync-tp-username",
    response_model=TPSyncResultDTO,
    status_code=status.HTTP_200_OK,
    summary="Sincronizar atleta con TrainingPeaks"
)
async def sync_tp_username(
    username: str = Query(..., description="Nombre/username del atleta en TrainingPeaks"),
    athlete_id: str = Query(..., description="ID del atleta en la base de datos"),
    db: AsyncSession = Depends(get_db)
) -> TPSyncResultDTO:
    """
    Sincroniza un atleta verificando que existe en TrainingPeaks.
    
    El proceso:
    1. Crea un driver de Selenium efimero (en thread separado para no bloquear)
    2. Hace login en TrainingPeaks
    3. Busca al atleta por el nombre proporcionado
    4. Si lo encuentra, guarda el nombre de TrainingPeaks en la base de datos
    5. Cierra el driver
    
    Las operaciones de Selenium se ejecutan en threads separados via run_selenium()
    para no bloquear el event loop y permitir que el healthcheck responda.
    
    Args:
        username: Nombre/username del atleta a buscar en TrainingPeaks
        athlete_id: ID del atleta en la base de datos local
        db: Sesion de base de datos (inyectado)
        
    Returns:
        TPSyncResultDTO: Resultado de la sincronizacion
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException
    
    from app.core.config import settings
    from app.infrastructure.driver.driver_manager import TRAININGPEAKS_URL
    from app.infrastructure.driver.services.auth_service import AuthService
    from app.infrastructure.driver.services.athlete_service import AthleteService
    from app.shared.exceptions.domain import AthleteNotFoundInTPException
    
    logger.info(f"Iniciando sincronizacion TP para atleta_id={athlete_id}, username={username}")
    
    # Verificar que el atleta existe en la base de datos
    repo = AthleteRepository(db)
    athlete = await repo.get_by_id(athlete_id)
    if athlete is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Atleta no encontrado: {athlete_id}"
        )
    
    def create_ephemeral_driver() -> tuple[webdriver.Chrome, WebDriverWait]:
        """Crea un driver efimero para la sincronizacion."""
        opts = Options()
        if settings.SELENIUM_HEADLESS:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-infobars")
        driver = webdriver.Chrome(options=opts)
        wait = WebDriverWait(driver, 10)
        driver.get(TRAININGPEAKS_URL)
        return driver, wait
    
    driver: Optional[webdriver.Chrome] = None
    found_name: Optional[str] = None
    found_group: Optional[str] = None
    
    try:
        # Crear driver en thread separado
        driver, wait = await run_selenium(create_ephemeral_driver)
        
        # Login en thread separado
        auth_service = AuthService(driver, wait)
        await run_selenium(auth_service.login_with_cookie)
        
        # Buscar atleta en thread separado
        athlete_service = AthleteService(driver, wait)
        try:
            await run_selenium(athlete_service.select_athlete, username)
            # Si llegamos aqui, el atleta fue encontrado y seleccionado
            found_name = username
            logger.info(f"Atleta encontrado en TrainingPeaks: {username}")
        except AthleteNotFoundInTPException as e:
            attempts = e.details.get("attempted_variations", [])
            logger.warning(f"Atleta no encontrado en TrainingPeaks: {username}. Intentos: {attempts}")
            return TPSyncResultDTO(
                success=False,
                username=username,
                tp_name=None,
                group=None,
                message=f"No se encontro el atleta '{username}' en TrainingPeaks"
            )
        except TimeoutException:
            logger.warning(f"Timeout buscando atleta en TrainingPeaks: {username}")
            return TPSyncResultDTO(
                success=False,
                username=username,
                tp_name=None,
                group=None,
                message=f"Timeout buscando el atleta '{username}' en TrainingPeaks"
            )
        
        # Guardar el resultado en la base de datos (en el campo performance)
        current_perf = athlete.performance if isinstance(athlete.performance, dict) else {}
        if current_perf is None:
            current_perf = {}
        
        current_perf["tp_sync"] = {
            "tp_username": username,
            "tp_name": found_name,
            "synced_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        }
        
        await repo.update(athlete_id, {"performance": current_perf})
        await db.commit()
        
        logger.info(f"Sincronizacion TP completada para atleta_id={athlete_id}")
        
        return TPSyncResultDTO(
            success=True,
            username=username,
            tp_name=found_name,
            group=found_group,
            message=f"Atleta '{found_name}' sincronizado correctamente con TrainingPeaks"
        )
        
    except Exception as e:
        logger.exception(f"Error en sincronizacion TP: {e}")
        return TPSyncResultDTO(
            success=False,
            username=username,
            tp_name=None,
            group=None,
            message=f"Error durante la sincronizacion: {str(e)}"
        )
        
    finally:
        # Cerrar driver en thread separado
        if driver is not None:
            try:
                await run_selenium(driver.quit)
            except Exception as e:
                logger.warning(f"Error cerrando driver efimero: {e}")
