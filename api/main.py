"""
Punto de entrada principal de la aplicación FastAPI.
Configura la aplicación, middlewares, rutas y eventos.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings, get_cors_origins
from app.core.events import startup_handler, shutdown_handler
from app.api.v1.router import api_router
from app.api.middlewares.error_handler import ErrorHandlerMiddleware
from app.shared.exceptions.base import AppException


def create_application() -> FastAPI:
    """
    Factory para crear y configurar la aplicación FastAPI.
    
    Returns:
        FastAPI: Instancia configurada de la aplicación
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Backend para gestión de agentes AutoGen",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configurar CORS
    cors_origins = get_cors_origins(settings.CORS_ORIGINS)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware personalizado para manejo de errores
    application.add_middleware(ErrorHandlerMiddleware)

    # Registrar eventos de inicio y cierre
    application.add_event_handler("startup", startup_handler(application))
    application.add_event_handler("shutdown", shutdown_handler(application))

    # Incluir routers de la API
    application.include_router(api_router, prefix="/api")

    # Manejador global de excepciones personalizadas
    @application.exception_handler(AppException)
    async def app_exception_handler(request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        )

    # Health check endpoint
    @application.get("/health", tags=["Health"])
    async def health_check():
        """Endpoint para verificar el estado de la aplicación."""
        return {
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT
        }

    return application


# Crear instancia de la aplicación
app = create_application()


if __name__ == "__main__":
    import uvicorn
    from loguru import logger
    
    # Determinar la URL base de acceso
    if settings.HOST == "0.0.0.0":
        access_host = "localhost"
    else:
        access_host = settings.HOST
    
    base_url = f"http://{access_host}:{settings.PORT}"
    
    # Mostrar las URLs disponibles
    logger.info("=" * 70)
    logger.info("URLS DISPONIBLES:")
    logger.info("=" * 70)
    logger.info(f"  Swagger UI:  {base_url}/docs")
    logger.info(f"  ReDoc:       {base_url}/redoc")
    logger.info(f"  OpenAPI:     {base_url}/openapi.json")
    logger.info(f"  Health:      {base_url}/health")
    logger.info("=" * 70)
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )

