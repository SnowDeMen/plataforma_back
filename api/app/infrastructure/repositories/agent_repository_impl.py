"""
Implementación del repositorio de agentes usando SQLAlchemy.
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.agent_repository import IAgentRepository
from app.domain.entities.agent import Agent
from app.infrastructure.database.models import AgentModel
from app.shared.exceptions.domain import EntityNotFoundException


class AgentRepositoryImpl(IAgentRepository):
    """Implementación del repositorio de agentes con SQLAlchemy."""
    
    def __init__(self, session: AsyncSession):
        """
        Inicializa el repositorio con una sesión de base de datos.
        
        Args:
            session: Sesión de SQLAlchemy
        """
        self.session = session
    
    async def create(self, agent: Agent) -> Agent:
        """Crea un nuevo agente en la base de datos."""
        db_agent = AgentModel(
            name=agent.name,
            type=agent.type,
            status=agent.status,
            configuration=agent.configuration,
            system_message=agent.system_message
        )
        
        self.session.add(db_agent)
        await self.session.flush()
        await self.session.refresh(db_agent)
        
        return self._to_entity(db_agent)
    
    async def get_by_id(self, agent_id: int) -> Optional[Agent]:
        """Obtiene un agente por su ID."""
        result = await self.session.execute(
            select(AgentModel).where(AgentModel.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()
        
        if db_agent is None:
            return None
        
        return self._to_entity(db_agent)
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Agent]:
        """Obtiene todos los agentes con paginación."""
        result = await self.session.execute(
            select(AgentModel).offset(skip).limit(limit)
        )
        db_agents = result.scalars().all()
        
        return [self._to_entity(db_agent) for db_agent in db_agents]
    
    async def update(self, agent: Agent) -> Agent:
        """Actualiza un agente existente."""
        result = await self.session.execute(
            select(AgentModel).where(AgentModel.id == agent.id)
        )
        db_agent = result.scalar_one_or_none()
        
        if db_agent is None:
            raise EntityNotFoundException("Agent", agent.id)
        
        db_agent.name = agent.name
        db_agent.type = agent.type
        db_agent.status = agent.status
        db_agent.configuration = agent.configuration
        db_agent.system_message = agent.system_message
        
        await self.session.flush()
        await self.session.refresh(db_agent)
        
        return self._to_entity(db_agent)
    
    async def delete(self, agent_id: int) -> bool:
        """Elimina un agente por su ID."""
        result = await self.session.execute(
            select(AgentModel).where(AgentModel.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()
        
        if db_agent is None:
            return False
        
        await self.session.delete(db_agent)
        return True
    
    async def get_by_name(self, name: str) -> Optional[Agent]:
        """Obtiene un agente por su nombre."""
        result = await self.session.execute(
            select(AgentModel).where(AgentModel.name == name)
        )
        db_agent = result.scalar_one_or_none()
        
        if db_agent is None:
            return None
        
        return self._to_entity(db_agent)
    
    @staticmethod
    def _to_entity(db_agent: AgentModel) -> Agent:
        """
        Convierte un modelo de base de datos a entidad de dominio.
        
        Args:
            db_agent: Modelo de SQLAlchemy
            
        Returns:
            Agent: Entidad de dominio
        """
        return Agent(
            id=db_agent.id,
            name=db_agent.name,
            type=db_agent.type,
            status=db_agent.status,
            configuration=db_agent.configuration or {},
            system_message=db_agent.system_message,
            created_at=db_agent.created_at,
            updated_at=db_agent.updated_at
        )

