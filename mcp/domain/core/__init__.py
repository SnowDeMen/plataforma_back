"""
Módulo Core - Gestión del driver y configuración global

Permite inyectar un driver externo ya inicializado para que
todas las funciones del dominio lo utilicen.
"""

from .driver_manager import (
    set_driver,
    is_driver_ready,
    ensure_driver,
    get_driver,
    get_wait,
    clear_driver
)

__all__ = [
    'set_driver',
    'is_driver_ready', 
    'ensure_driver',
    'get_driver',
    'get_wait',
    'clear_driver'
]
