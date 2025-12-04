"""
Dependencias para inyección de repositorios.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.infrastructure.repositories.agent_repository_impl import AgentRepositoryImpl


async def get_agent_repository(
    session: AsyncSession = Depends(get_db)
) -> AgentRepositoryImpl:
    """
    Dependencia para obtener el repositorio de agentes.
    
    Args:
        session: Sesión de base de datos
        
    Returns:
        AgentRepositoryImpl: Instancia del repositorio de agentes
    """
    return AgentRepositoryImpl(session)

