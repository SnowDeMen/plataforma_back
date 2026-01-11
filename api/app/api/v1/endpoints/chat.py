"""
Endpoints para operaciones de chat.
Maneja el envio y recepcion de mensajes del agente de chat.
"""
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, status

from app.application.use_cases.chat_use_cases import ChatUseCases
from app.application.dto.chat_dto import (
    ChatRequestDTO,
    ChatResponseDTO,
    ChatHistoryDTO,
    ChatSessionInfoDTO,
    ChatConfigUpdateDTO
)
from app.api.v1.dependencies.use_case_deps import get_chat_use_cases
from app.shared.utils.audit_logger import AuditLogger


router = APIRouter(prefix="/sessions/{session_id}/chat", tags=["Chat"])


@router.post(
    "/",
    response_model=ChatResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Enviar mensaje al chat"
)
async def send_message(
    session_id: str,
    dto: ChatRequestDTO,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> ChatResponseDTO:
    """
    Envia un mensaje al agente de chat y obtiene su respuesta.
    
    El mensaje se procesa con el agente asociado a la sesion
    y se persiste en el historial de la base de datos.
    
    Args:
        session_id: ID de la sesion de entrenamiento
        dto: Datos del mensaje a enviar
        use_cases: Casos de uso de chat (inyectado)
        
    Returns:
        ChatResponseDTO: Respuesta del agente
        
    Raises:
        404: Si la sesion no existe
    """
    start_time = time.time()
    
    # Asegurar que el session_logger existe antes de loguear
    # (necesario para sesiones reanudadas donde el logger no existe en memoria)
    await use_cases.ensure_session_logger(session_id)
    
    # Log de la request
    AuditLogger.log_request(
        session_id=session_id,
        method="POST",
        path=f"/api/v1/sessions/{session_id}/chat/",
        body={"message": dto.message[:100] + "..." if len(dto.message) > 100 else dto.message}
    )
    
    # Procesar mensaje
    response = await use_cases.send_message(session_id, dto)
    
    # Log de la response
    duration_ms = (time.time() - start_time) * 1000
    AuditLogger.log_response(
        session_id=session_id,
        method="POST",
        path=f"/api/v1/sessions/{session_id}/chat/",
        status_code=200,
        body={"message": response.message[:100] + "..." if len(response.message) > 100 else response.message},
        duration_ms=duration_ms
    )
    
    return response


@router.get(
    "/history",
    response_model=ChatHistoryDTO,
    summary="Obtener historial de chat"
)
async def get_history(
    session_id: str,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> ChatHistoryDTO:
    """
    Obtiene el historial completo de mensajes de una sesion de chat.
    
    Retorna todos los mensajes ordenados cronologicamente.
    
    Args:
        session_id: ID de la sesion
        use_cases: Casos de uso de chat (inyectado)
        
    Returns:
        ChatHistoryDTO: Historial completo de la sesion
        
    Raises:
        404: Si la sesion no existe
    """
    return await use_cases.get_history(session_id)


@router.get(
    "/info",
    response_model=ChatSessionInfoDTO,
    summary="Obtener informacion del chat"
)
async def get_session_info(
    session_id: str,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> ChatSessionInfoDTO:
    """
    Obtiene informacion resumida de la sesion de chat.
    
    Incluye conteo de mensajes y ultimo mensaje.
    
    Args:
        session_id: ID de la sesion
        use_cases: Casos de uso de chat (inyectado)
        
    Returns:
        ChatSessionInfoDTO: Informacion resumida
        
    Raises:
        404: Si la sesion no existe
    """
    return await use_cases.get_session_info(session_id)


@router.patch(
    "/config",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Actualizar configuracion del chat"
)
async def update_config(
    session_id: str,
    dto: ChatConfigUpdateDTO,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> None:
    """
    Actualiza la configuracion del agente de chat.
    
    Permite cambiar el system message para modificar el comportamiento.
    
    Args:
        session_id: ID de la sesion
        dto: Datos de configuracion a actualizar
        use_cases: Casos de uso de chat (inyectado)
        
    Raises:
        404: Si la sesion no existe
    """
    await use_cases.update_config(session_id, dto)


@router.delete(
    "/history",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Limpiar historial de chat"
)
async def clear_history(
    session_id: str,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> None:
    """
    Limpia el historial de mensajes de la sesion.
    
    Esto reinicia la conversacion manteniendo la sesion activa.
    
    Args:
        session_id: ID de la sesion
        use_cases: Casos de uso de chat (inyectado)
        
    Raises:
        404: Si la sesion no existe
    """
    await use_cases.clear_history(session_id)


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar sesion de chat permanentemente"
)
async def delete_chat_session(
    session_id: str,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> None:
    """
    Elimina permanentemente una sesion de chat de la base de datos.
    
    Esta accion no se puede deshacer.
    
    Args:
        session_id: ID de la sesion a eliminar
        use_cases: Casos de uso de chat (inyectado)
        
    Raises:
        404: Si la sesion no existe
    """
    await use_cases.delete_session(session_id)


# Endpoint adicional para listar sesiones de un atleta (fuera del prefijo de session_id)
athlete_router = APIRouter(prefix="/athletes", tags=["Chat"])


@athlete_router.get(
    "/{athlete_name}/chat-sessions",
    response_model=List[ChatSessionInfoDTO],
    summary="Listar sesiones de chat de un atleta"
)
async def get_athlete_sessions(
    athlete_name: str,
    athlete_id: Optional[str] = None,
    active_only: bool = True,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> List[ChatSessionInfoDTO]:
    """
    Obtiene todas las sesiones de chat de un atleta.
    
    Util para mostrar el historial de conversaciones y permitir
    al usuario retomar una conversacion previa.
    
    Args:
        athlete_name: Nombre del atleta
        active_only: Si solo retornar sesiones activas (default: True)
        use_cases: Casos de uso de chat (inyectado)
        
    Returns:
        Lista de ChatSessionInfoDTO con las sesiones del atleta
    """
    return await use_cases.get_athlete_sessions(athlete_name, athlete_id, active_only)


@athlete_router.delete(
    "/chat-sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar sesion de chat permanentemente"
)
async def delete_session_permanently(
    session_id: str,
    use_cases: ChatUseCases = Depends(get_chat_use_cases)
) -> None:
    """
    Elimina permanentemente una sesion de chat de la base de datos.
    
    Esta accion no se puede deshacer. Elimina todo el historial de mensajes.
    
    Args:
        session_id: ID de la sesion a eliminar
        use_cases: Casos de uso de chat (inyectado)
        
    Raises:
        404: Si la sesion no existe
    """
    await use_cases.delete_session(session_id)


