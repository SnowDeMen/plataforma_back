"""
Dependencias para inyeccion de casos de uso.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.agent_use_cases import AgentUseCases
from app.application.use_cases.auth_use_cases import AuthUseCases
from app.application.use_cases.session_use_cases import SessionUseCases
from app.application.use_cases.chat_use_cases import ChatUseCases
from app.application.use_cases.athlete_use_cases import AthleteUseCases
from app.application.use_cases.training_history_use_cases import TrainingHistoryUseCases
from app.application.use_cases.tp_sync_use_cases import TPSyncUseCases
from app.domain.repositories.agent_repository import IAgentRepository
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.api.v1.dependencies.repository_deps import get_agent_repository
from app.core.config import settings
from app.infrastructure.database.session import get_db
from app.infrastructure.security.single_user_auth_service import SingleUserAuthService


async def get_agent_use_cases(
    agent_repository: IAgentRepository = Depends(get_agent_repository)
) -> AgentUseCases:
    """
    Dependencia para obtener los casos de uso de agentes.
    
    Args:
        agent_repository: Repositorio de agentes
        
    Returns:
        AgentUseCases: Instancia de casos de uso de agentes
    """
    return AgentUseCases(agent_repository)


def get_session_use_cases(
    db: AsyncSession = Depends(get_db)
) -> SessionUseCases:
    """
    Dependencia para obtener los casos de uso de sesiones.
    
    Returns:
        SessionUseCases: Instancia de casos de uso de sesiones
    """
    return SessionUseCases(db)


def get_training_history_use_cases() -> TrainingHistoryUseCases:
    """
    Dependencia para obtener los casos de uso de historial de entrenamientos.

    Nota: este caso de uso administra jobs en memoria, por lo que no requiere
    una sesión de DB request-scoped.
    """
    return TrainingHistoryUseCases()


def get_tp_sync_use_cases() -> TPSyncUseCases:
    """
    Dependencia para obtener los casos de uso de sincronizacion TP.
    
    Nota: este caso de uso administra jobs en memoria (similar a training_history),
    por lo que no requiere una sesion de DB request-scoped.
    """
    return TPSyncUseCases()


async def get_chat_use_cases(
    db: AsyncSession = Depends(get_db)
) -> ChatUseCases:
    """
    Dependencia para obtener los casos de uso de chat.
    
    Args:
        db: Sesion de base de datos
        
    Returns:
        ChatUseCases: Instancia de casos de uso de chat
    """
    return ChatUseCases(db)


async def get_athlete_use_cases(
    db: AsyncSession = Depends(get_db)
) -> AthleteUseCases:
    """
    Dependencia para obtener los casos de uso de atletas.
    
    Args:
        db: Sesion de base de datos
        
    Returns:
        AthleteUseCases: Instancia de casos de uso de atletas
    """
    return AthleteUseCases(db)


def get_auth_use_cases() -> AuthUseCases:
    """
    Dependencia para obtener los casos de uso de autenticación (login único).
    """
    auth_service = SingleUserAuthService(
        expected_username=settings.AUTH_USERNAME,
        expected_password=settings.AUTH_PASSWORD,
    )
    return AuthUseCases(auth_service)
