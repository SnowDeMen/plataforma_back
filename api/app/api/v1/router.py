"""
Router principal de la API v1.
Agrupa todos los endpoints de la version 1.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import agents, sessions, chat, plans, plan_ws, athletes, auth, training_history, sync, admin


# Router principal de la API v1
api_router = APIRouter(prefix="/v1")

# Incluir routers de endpoints especificos
api_router.include_router(agents.router)
api_router.include_router(auth.router)
api_router.include_router(sessions.router)
api_router.include_router(chat.router)
api_router.include_router(chat.athlete_router)
api_router.include_router(plans.router)
api_router.include_router(plan_ws.router)
api_router.include_router(athletes.router)
api_router.include_router(training_history.router)
api_router.include_router(sync.router)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

