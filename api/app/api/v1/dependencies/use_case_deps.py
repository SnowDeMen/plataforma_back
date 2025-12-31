"""
Dependencias para inyeccion de casos de uso.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.agent_use_cases import AgentUseCases
from app.application.use_cases.session_use_cases import SessionUseCases
from app.application.use_cases.chat_use_cases import ChatUseCases
from app.application.use_cases.athlete_use_cases import AthleteUseCases
from app.domain.repositories.agent_repository import IAgentRepository
from app.api.v1.dependencies.repository_deps import get_agent_repository
from app.infrastructure.database.session import get_db


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
