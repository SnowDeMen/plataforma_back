"""
Interfaz del repositorio de agentes.
Define el contrato que debe cumplir cualquier implementación.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.entities.agent import Agent


class IAgentRepository(ABC):
    """
    Interfaz del repositorio de agentes.
    Define las operaciones de persistencia para agentes.
    """
    
    @abstractmethod
    async def create(self, agent: Agent) -> Agent:
        """
        Crea un nuevo agente en la base de datos.
        
        Args:
            agent: Entidad del agente a crear
            
        Returns:
            Agent: Agente creado con ID asignado
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, agent_id: int) -> Optional[Agent]:
        """
        Obtiene un agente por su ID.
        
        Args:
            agent_id: ID del agente
            
        Returns:
            Optional[Agent]: Agente encontrado o None
        """
        pass
    
    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Agent]:
        """
        Obtiene todos los agentes con paginación.
        
        Args:
            skip: Número de registros a saltar
            limit: Número máximo de registros a retornar
            
        Returns:
            List[Agent]: Lista de agentes
        """
        pass
    
    @abstractmethod
    async def update(self, agent: Agent) -> Agent:
        """
        Actualiza un agente existente.
        
        Args:
            agent: Entidad del agente con datos actualizados
            
        Returns:
            Agent: Agente actualizado
        """
        pass
    
    @abstractmethod
    async def delete(self, agent_id: int) -> bool:
        """
        Elimina un agente por su ID.
        
        Args:
            agent_id: ID del agente a eliminar
            
        Returns:
            bool: True si se eliminó correctamente
        """
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Agent]:
        """
        Obtiene un agente por su nombre.
        
        Args:
            name: Nombre del agente
            
        Returns:
            Optional[Agent]: Agente encontrado o None
        """
        pass

