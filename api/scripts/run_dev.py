"""
Script para ejecutar el servidor en modo desarrollo.
"""
import uvicorn
from app.core.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )

