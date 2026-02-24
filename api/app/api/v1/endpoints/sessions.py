"""
Endpoints para operaciones con sesiones de entrenamiento.
Maneja la creacion, consulta y cierre de sesiones con drivers de Selenium.
Incluye inicializacion automatica del agente de chat.
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
    3. Creacion del agente de chat asociado a la sesion
    4. Persistencia de la sesion de chat en base de datos
    
    Args:
        dto: Datos de inicio con el nombre del atleta
        use_cases: Casos de uso de sesiones (inyectado)
        db: Sesion de base de datos (inyectado)
        
    Returns:
        SessionResponseDTO: Informacion de la sesion iniciada con chat activo
        
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
    
    # 2. Inicializar agente de chat para esta sesion
    chat_repo = ChatRepository(db)
    
    # Crear registro de chat en base de datos
    await chat_repo.create(
        session_id=session_response.session_id,
        athlete_name=session_response.athlete_name,
        athlete_id=session_response.athlete_id,
        system_message=None,  # Usara el default del ChatManager
        agent_config={}
    )
    
    # 3. Crear agente en memoria con contexto del atleta
    ChatManager.create_agent(
        session_id=session_response.session_id,
        athlete_name=session_response.athlete_name,
        athlete_info=dto.athlete_info
    )
    
    # Log del agente creado
    AuditLogger.log_event(
        session_id=session_response.session_id,
        event="CHAT_AGENT_CREATED",
        details={}
    )
    
    # Construir mensaje de respuesta
    session_response.message = (
        f"Sesion iniciada para {dto.athlete_name}. "
        f"Chat: /api/v1/sessions/{session_response.session_id}/chat/"
    )
    
    return session_response


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
    
    # Cerrar driver de Selenium
    use_cases.close_session(session_id)
    
    # Desactivar sesion de chat en BD
    chat_repo = ChatRepository(db)
    await chat_repo.deactivate(session_id)
    
    # Eliminar agente de memoria
    ChatManager.remove_agent(session_id)
    
    # Cerrar el logger de sesion
    AuditLogger.close_session(session_id)


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
    
    # 3. Asegurar que el agente este listo (recargar si es necesario)
    # ChatManager.get_agent(session_id) validara o recreara el agente si no existe
    
    session_response.message = "Sesion reiniciada correctamente."
    
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
