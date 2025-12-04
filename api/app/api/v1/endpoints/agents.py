"""
Endpoints para operaciones con agentes.
"""
from typing import List
from fastapi import APIRouter, Depends, status

from app.application.use_cases.agent_use_cases import AgentUseCases
from app.application.dto.agent_dto import (
    AgentCreateDTO,
    AgentUpdateDTO,
    AgentResponseDTO
)
from app.api.v1.dependencies.use_case_deps import get_agent_use_cases


router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post(
    "/",
    response_model=AgentResponseDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo agente"
)
async def create_agent(
    dto: AgentCreateDTO,
    use_cases: AgentUseCases = Depends(get_agent_use_cases)
) -> AgentResponseDTO:
    """
    Crea un nuevo agente de AutoGen.
    
    Args:
        dto: Datos del agente a crear
        use_cases: Casos de uso de agentes (inyectado)
        
    Returns:
        AgentResponseDTO: Agente creado
    """
    return await use_cases.create_agent(dto)


@router.get(
    "/{agent_id}",
    response_model=AgentResponseDTO,
    summary="Obtener un agente por ID"
)
async def get_agent(
    agent_id: int,
    use_cases: AgentUseCases = Depends(get_agent_use_cases)
) -> AgentResponseDTO:
    """
    Obtiene un agente específico por su ID.
    
    Args:
        agent_id: ID del agente
        use_cases: Casos de uso de agentes (inyectado)
        
    Returns:
        AgentResponseDTO: Agente encontrado
    """
    return await use_cases.get_agent(agent_id)


@router.get(
    "/",
    response_model=List[AgentResponseDTO],
    summary="Listar todos los agentes"
)
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    use_cases: AgentUseCases = Depends(get_agent_use_cases)
) -> List[AgentResponseDTO]:
    """
    Lista todos los agentes con paginación.
    
    Args:
        skip: Número de registros a saltar
        limit: Número máximo de registros a retornar
        use_cases: Casos de uso de agentes (inyectado)
        
    Returns:
        List[AgentResponseDTO]: Lista de agentes
    """
    return await use_cases.list_agents(skip, limit)


@router.put(
    "/{agent_id}",
    response_model=AgentResponseDTO,
    summary="Actualizar un agente"
)
async def update_agent(
    agent_id: int,
    dto: AgentUpdateDTO,
    use_cases: AgentUseCases = Depends(get_agent_use_cases)
) -> AgentResponseDTO:
    """
    Actualiza un agente existente.
    
    Args:
        agent_id: ID del agente a actualizar
        dto: Datos a actualizar
        use_cases: Casos de uso de agentes (inyectado)
        
    Returns:
        AgentResponseDTO: Agente actualizado
    """
    return await use_cases.update_agent(agent_id, dto)


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un agente"
)
async def delete_agent(
    agent_id: int,
    use_cases: AgentUseCases = Depends(get_agent_use_cases)
) -> None:
    """
    Elimina un agente.
    
    Args:
        agent_id: ID del agente a eliminar
        use_cases: Casos de uso de agentes (inyectado)
    """
    await use_cases.delete_agent(agent_id)

