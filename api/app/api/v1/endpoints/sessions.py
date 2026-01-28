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
from app.application.use_cases.tp_sync_use_cases import TPSyncUseCases
from app.application.dto.session_dto import (
    SessionStartDTO, 
    SessionResponseDTO, 
    TPSyncResultDTO,
    TPSyncJobResponseDTO,
    TPSyncJobStatusDTO,
)
from app.api.v1.dependencies.use_case_deps import get_session_use_cases, get_tp_sync_use_cases
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


@router.post(
    "/sync-tp-username",
    status_code=status.HTTP_200_OK,
    summary="Sincronizar nombre de atleta desde TrainingPeaks"
)
async def sync_tp_username(
    username: str,
    athlete_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Busca un atleta en TrainingPeaks por username y guarda su nombre (tp_name).
    
    Flujo:
    1. Busca el atleta por username en TrainingPeaks
    2. Si lo encuentra, obtiene el nombre del atleta en TP
    3. Guarda el nombre como tp_name en PostgreSQL
    4. Actualiza el campo tp_name en Airtable
    
    Args:
        username: Username de TrainingPeaks (tp_username)
        athlete_id: ID del atleta en la base de datos
        db: Sesion de base de datos
    
    Returns:
        Dict con success, tp_name, message
    """
    from app.infrastructure.driver.services.auth_service import AuthService
    from app.infrastructure.driver.services.athlete_service import AthleteService
    from app.infrastructure.repositories.athlete_repository import AthleteRepository
    from app.infrastructure.external.airtable_sync.airtable_client import (
        AirtableClient, AirtableCredentials
    )
    import os
    
    driver = None
    result = {
        "success": False,
        "message": "",
        "username": username,
        "tp_name": None,
        "group": None
    }
    
    try:
        # 1. Crear driver navegando a #home
        logger.info(f"[sync-tp-username] Buscando atleta con username: {username}")
        driver, wait = DriverManager._create_driver_for_home()
        
        # Inicializar servicios
        auth_service = AuthService(driver, wait)
        athlete_service = AthleteService(driver, wait)
        
        # 2. Login en TrainingPeaks
        logger.info("[sync-tp-username] Haciendo login...")
        auth_service.login_with_cookie()
        
        # 3. Navegar a #home
        logger.info("[sync-tp-username] Navegando a #home...")
        athlete_service.navigate_to_home()
        
        # 4. Buscar por username
        search_result = athlete_service.find_athlete_by_username(username)
        
        if not search_result["found"]:
            result["message"] = f"No se encontro atleta con username: {username}"
            return result
        
        tp_name = search_result["full_name"]
        result["tp_name"] = tp_name
        result["group"] = search_result["group"]
        
        # 5. Guardar en PostgreSQL
        logger.info(f"[sync-tp-username] Guardando tp_name: {tp_name} para atleta {athlete_id}")
        repo = AthleteRepository(db)
        athlete = await repo.get_by_id(athlete_id)
        
        if not athlete:
            result["message"] = f"Atleta no encontrado en DB: {athlete_id}"
            return result
        
        # Actualizar tp_name en la base de datos
        await repo.update(athlete_id, {"tp_name": tp_name})
        await db.commit()
        
        # 6. Actualizar en Airtable (usando IDs directos)
        airtable_record_id = athlete.id  # El ID del atleta es el record_id de Airtable
        AIRTABLE_TABLE_ID = "tblMNRYRfYTWYpc5o"  # Table ID de Formulario_Inicial
        TP_NAME_FIELD_ID = "fldmVrBQxHtlN4qXL"  # Field ID de tp_name
        
        try:
            airtable_token = os.environ.get("AIRTABLE_TOKEN")
            airtable_base_id = os.environ.get("AIRTABLE_BASE_ID")
            
            if airtable_token and airtable_base_id:
                client = AirtableClient(
                    AirtableCredentials(token=airtable_token, base_id=airtable_base_id)
                )
                logger.info(f"[sync-tp-username] Actualizando Airtable: table={AIRTABLE_TABLE_ID}, record={airtable_record_id}")
                client.update_record(
                    table_name=AIRTABLE_TABLE_ID,
                    record_id=airtable_record_id,
                    fields={TP_NAME_FIELD_ID: tp_name}
                )
                logger.info(f"[sync-tp-username] Airtable actualizado exitosamente: {airtable_record_id} -> {tp_name}")
            else:
                logger.warning("[sync-tp-username] Credenciales de Airtable no configuradas")
        except Exception as e:
            logger.exception(f"[sync-tp-username] Error actualizando Airtable: {e}")
            # No fallar el endpoint si Airtable falla
        
        result["success"] = True
        result["message"] = f"Sincronizado exitosamente: {tp_name}"
        logger.info(f"[sync-tp-username] Exito: {username} -> {tp_name}")
        
        return result
        
    except Exception as e:
        logger.exception(f"[sync-tp-username] Error: {e}")
        result["message"] = f"Error: {str(e)}"
        return result
        
    finally:
        # Cerrar driver
        if driver:
            try:
                driver.quit()
                logger.info("[test-home-settings] Driver cerrado")
            except Exception:
                pass


# ============================================================================
# ENDPOINTS CON PARAMETRO {session_id}
# ============================================================================

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
    response_model=TPSyncJobResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Iniciar sincronizacion de nombre de atleta desde TrainingPeaks"
)
async def sync_tp_username(
    username: str,
    athlete_id: str,
    use_cases: TPSyncUseCases = Depends(get_tp_sync_use_cases),
) -> TPSyncJobResponseDTO:
    """
    Inicia un job asincrono para buscar un atleta en TrainingPeaks por username.
    
    El endpoint retorna inmediatamente con un job_id. El frontend debe hacer
    polling al endpoint GET /sync-tp-username/jobs/{job_id} para obtener el
    estado y resultado final.
    
    Flujo del job en background:
    1. Crea driver navegando a #home
    2. Hace login en TrainingPeaks
    3. Busca el atleta por username iterando por todos los grupos
    4. Si lo encuentra, guarda el tp_name en PostgreSQL y Airtable
    
    Args:
        username: Username de TrainingPeaks (tp_username)
        athlete_id: ID del atleta en la base de datos
        use_cases: Casos de uso de sincronizacion TP (inyectado)
    
    Returns:
        TPSyncJobResponseDTO: Respuesta con job_id para polling
    """
    return await use_cases.start_sync(username=username, athlete_id=athlete_id)


@router.get(
    "/sync-tp-username/jobs/{job_id}",
    response_model=TPSyncJobStatusDTO,
    summary="Obtener estado de un job de sincronizacion TP (polling)"
)
async def get_tp_sync_job_status(
    job_id: str,
    use_cases: TPSyncUseCases = Depends(get_tp_sync_use_cases),
) -> TPSyncJobStatusDTO:
    """
    Retorna el estado actual del job de sincronizacion.
    
    El frontend debe hacer polling a este endpoint cada 2 segundos hasta que
    el status sea 'completed' o 'failed'.
    
    Cuando status == 'completed':
    - tp_name contiene el nombre encontrado en TrainingPeaks
    - group contiene el grupo donde se encontro el atleta
    
    Cuando status == 'failed':
    - error contiene el mensaje de error
    
    Args:
        job_id: ID del job a consultar
        use_cases: Casos de uso de sincronizacion TP (inyectado)
        
    Returns:
        TPSyncJobStatusDTO: Estado actual del job
        
    Raises:
        404: Si el job no existe
    """
    try:
        return await use_cases.get_job_status(job_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Job no encontrado"
        )
