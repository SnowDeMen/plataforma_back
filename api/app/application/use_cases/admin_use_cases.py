"""
Casos de uso para administración del sistema.
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.repositories.system_settings_repository import SystemSettingsRepository
from loguru import logger

class AdminUseCases:
    """
    Gestiona configuraciones globales y mantenimiento del sistema.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings_repo = SystemSettingsRepository(db)

    async def get_system_settings(self) -> Dict[str, Any]:
        """
        Retorna todas las configuraciones actuales.
        """
        return await self.settings_repo.get_all()

    async def update_notification_interval(self, hours: float) -> bool:
        """
        Actualiza el intervalo de notificaciones de Telegram.
        Nota: El efecto real en el scheduler ocurrirá en el próximo reinicio
        o mediante un trigger en el endpoint que actualice el job activo.
        """
        if hours <= 0:
            return False
            
        await self.settings_repo.set_value(
            "telegram_notification_interval_hours", 
            hours,
            "Frecuencia con la que se envían alertas de atletas pendientes (horas)."
        )
        await self.db.commit()
        logger.info(f"Intervalo de notificaciones actualizado a {hours}h")
        return True

    async def seed_default_settings(self) -> None:
        """
        Puebla configuraciones iniciales si no existen.
        """
        settings = [
            {
                "key": "telegram_notification_interval_hours",
                "value": 24.0,
                "description": "Frecuencia con la que se envían alertas de atletas pendientes (horas)."
            }
        ]
        
        for s in settings:
            # Solo si no existe
            val = await self.settings_repo.get_value(s["key"])
            if val is None:
                await self.settings_repo.set_value(s["key"], s["value"], s["description"])
        
        await self.db.commit()
        logger.info("Configuraciones por defecto inicializadas")
