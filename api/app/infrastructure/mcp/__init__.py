"""
Modulo de integracion con el servidor MCP de TrainingPeaks.
Gestiona la conexion entre las sesiones de entrenamiento y el servidor MCP.
"""
from .mcp_server_manager import MCPServerManager
from .mcp_tools import MCPToolsAdapter

__all__ = ["MCPServerManager", "MCPToolsAdapter"]

