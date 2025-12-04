"""
Casos de uso relacionados con agentes.
"""
from typing import List

from app.domain.repositories.agent_repository import IAgentRepository
from app.domain.entities.agent import Agent
from app.application.dto.agent_dto import (
    AgentCreateDTO,
    AgentUpdateDTO,
    AgentResponseDTO
)
from app.shared.exceptions.domain import (
    EntityNotFoundException,
    EntityAlreadyExistsException
)


class AgentUseCases:
    """
    Casos de uso para operaciones con agentes.
    Orquesta la lógica de aplicación entre repositorios y servicios.
    """
    
    def __init__(self, agent_repository: IAgentRepository):
        """
        Inicializa los casos de uso con sus dependencias.
        
        Args:
            agent_repository: Repositorio de agentes
        """
        self.agent_repository = agent_repository
    
    async def create_agent(self, dto: AgentCreateDTO) -> AgentResponseDTO:
        """
        Crea un nuevo agente.
        
        Args:
            dto: Datos del agente a crear
            
        Returns:
            AgentResponseDTO: Agente creado
            
        Raises:
            EntityAlreadyExistsException: Si ya existe un agente con ese nombre
        """
        # Verificar que no exista un agente con el mismo nombre
        existing_agent = await self.agent_repository.get_by_name(dto.name)
        if existing_agent:
            raise EntityAlreadyExistsException("Agent", "name", dto.name)
        
        # Crear entidad de dominio
        agent = Agent(
            name=dto.name,
            type=dto.type,
            system_message=dto.system_message,
            configuration=dto.configuration or {}
        )
        
        # Persistir en base de datos
        created_agent = await self.agent_repository.create(agent)
        
        # Convertir a DTO de respuesta
        return self._to_response_dto(created_agent)
    
    async def get_agent(self, agent_id: int) -> AgentResponseDTO:
        """
        Obtiene un agente por su ID.
        
        Args:
            agent_id: ID del agente
            
        Returns:
            AgentResponseDTO: Agente encontrado
            
        Raises:
            EntityNotFoundException: Si no se encuentra el agente
        """
        agent = await self.agent_repository.get_by_id(agent_id)
        
        if agent is None:
            raise EntityNotFoundException("Agent", agent_id)
        
        return self._to_response_dto(agent)
    
    async def list_agents(self, skip: int = 0, limit: int = 100) -> List[AgentResponseDTO]:
        """
        Lista todos los agentes con paginación.
        
        Args:
            skip: Número de registros a saltar
            limit: Número máximo de registros
            
        Returns:
            List[AgentResponseDTO]: Lista de agentes
        """
        agents = await self.agent_repository.get_all(skip, limit)
        return [self._to_response_dto(agent) for agent in agents]
    
    async def update_agent(self, agent_id: int, dto: AgentUpdateDTO) -> AgentResponseDTO:
        """
        Actualiza un agente existente.
        
        Args:
            agent_id: ID del agente a actualizar
            dto: Datos a actualizar
            
        Returns:
            AgentResponseDTO: Agente actualizado
            
        Raises:
            EntityNotFoundException: Si no se encuentra el agente
        """
        # Obtener agente existente
        agent = await self.agent_repository.get_by_id(agent_id)
        if agent is None:
            raise EntityNotFoundException("Agent", agent_id)
        
        # Actualizar campos si se proporcionan
        if dto.name is not None:
            agent.name = dto.name
        if dto.system_message is not None:
            agent.system_message = dto.system_message
        if dto.configuration is not None:
            agent.update_configuration(dto.configuration)
        if dto.status is not None:
            agent.status = dto.status
        
        # Persistir cambios
        updated_agent = await self.agent_repository.update(agent)
        
        return self._to_response_dto(updated_agent)
    
    async def delete_agent(self, agent_id: int) -> bool:
        """
        Elimina un agente.
        
        Args:
            agent_id: ID del agente a eliminar
            
        Returns:
            bool: True si se eliminó correctamente
            
        Raises:
            EntityNotFoundException: Si no se encuentra el agente
        """
        success = await self.agent_repository.delete(agent_id)
        
        if not success:
            raise EntityNotFoundException("Agent", agent_id)
        
        return success
    
    @staticmethod
    def _to_response_dto(agent: Agent) -> AgentResponseDTO:
        """
        Convierte una entidad de dominio a DTO de respuesta.
        
        Args:
            agent: Entidad de dominio
            
        Returns:
            AgentResponseDTO: DTO de respuesta
        """
        return AgentResponseDTO(
            id=agent.id,
            name=agent.name,
            type=agent.type,
            status=agent.status,
            configuration=agent.configuration,
            system_message=agent.system_message,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        )

