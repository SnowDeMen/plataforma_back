"""
Router principal de la API v1.
Agrupa todos los endpoints de la version 1.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import agents, sessions, chat


# Router principal de la API v1
api_router = APIRouter(prefix="/v1")

# Incluir routers de endpoints especificos
api_router.include_router(agents.router)
api_router.include_router(sessions.router)
api_router.include_router(chat.router)
api_router.include_router(chat.athlete_router)

