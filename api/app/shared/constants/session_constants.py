"""
Constantes relacionadas con sesiones de consulta de entrenamientos.
Define estados, atletas válidos y configuraciones de sesión.
"""
from enum import Enum


class SessionStatus(str, Enum):
    """Estados posibles de una sesión de consulta de entrenamientos."""
    INITIALIZING = "initializing"
    SELECTING_ATHLETE = "selecting_athlete"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    ERROR = "error"
