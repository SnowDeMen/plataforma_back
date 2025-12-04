"""
Middleware para manejo centralizado de errores.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware para capturar y manejar errores de forma centralizada."""
    
    async def dispatch(self, request: Request, call_next):
        """
        Procesa la petición y captura errores.
        
        Args:
            request: Petición HTTP
            call_next: Siguiente middleware/handler
            
        Returns:
            Response: Respuesta HTTP
        """
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Log del error (escapar llaves para evitar error de formato en loguru)
            error_msg = str(exc).replace("{", "{{").replace("}", "}}")
            logger.error(f"Error no manejado: {error_msg}", exc_info=True)
            
            # Respuesta de error generica
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "INTERNAL_SERVER_ERROR",
                    "message": "Ha ocurrido un error interno del servidor",
                    "details": {}
                }
            )

