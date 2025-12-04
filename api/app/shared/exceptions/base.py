"""
Excepción base para todas las excepciones personalizadas de la aplicación.
"""
from typing import Optional, Dict, Any


class AppException(Exception):
    """
    Excepción base de la aplicación.
    Todas las excepciones personalizadas deben heredar de esta clase.
    """
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Inicializa la excepción.
        
        Args:
            message: Mensaje de error descriptivo
            status_code: Código de estado HTTP
            error_code: Código de error personalizado
            details: Detalles adicionales del error
        """
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

