"""
Tests unitarios para la entidad Agent.
"""
import pytest

from app.domain.entities.agent import Agent
from app.shared.constants.agent_constants import AgentType, AgentStatus


def test_create_agent():
    """Test de creación de un agente."""
    agent = Agent(
        name="Test Agent",
        type=AgentType.ASSISTANT,
        system_message="Test message"
    )
    
    assert agent.name == "Test Agent"
    assert agent.type == AgentType.ASSISTANT
    assert agent.status == AgentStatus.IDLE
    assert agent.system_message == "Test message"


def test_agent_without_name_raises_error():
    """Test que verifica que un agente sin nombre lanza error."""
    with pytest.raises(ValueError):
        Agent(name="", type=AgentType.ASSISTANT)


def test_agent_activate():
    """Test de activación de un agente."""
    agent = Agent(name="Test Agent", type=AgentType.ASSISTANT)
    agent.activate()
    
    assert agent.status == AgentStatus.RUNNING
    assert agent.is_active()


def test_agent_pause():
    """Test de pausa de un agente."""
    agent = Agent(name="Test Agent", type=AgentType.ASSISTANT)
    agent.activate()
    agent.pause()
    
    assert agent.status == AgentStatus.PAUSED
    assert not agent.is_active()


def test_agent_complete():
    """Test de completar un agente."""
    agent = Agent(name="Test Agent", type=AgentType.ASSISTANT)
    agent.complete()
    
    assert agent.status == AgentStatus.COMPLETED


def test_agent_update_configuration():
    """Test de actualización de configuración."""
    agent = Agent(
        name="Test Agent",
        type=AgentType.ASSISTANT,
        configuration={"key1": "value1"}
    )
    
    agent.update_configuration({"key2": "value2"})
    
    assert agent.configuration["key1"] == "value1"
    assert agent.configuration["key2"] == "value2"

