"""
Repositorio para gestionar configuraciones del sistema.
"""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from loguru import logger

from app.infrastructure.database.models import SystemSettingsModel

class SystemSettingsRepository:
    """
    Gestiona la tabla system_settings.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_value(self, key: str, default: Any = None) -> Any:
        """
        Obtiene el valor de una configuración por su clave.
        """
        query = select(SystemSettingsModel).where(SystemSettingsModel.key == key)
        result = await self.db.execute(query)
        setting = result.scalar_one_or_none()
        return setting.value if setting else default

    async def get_all(self) -> Dict[str, Any]:
        """
        Obtiene todas las configuraciones como un diccionario.
        """
        query = select(SystemSettingsModel)
        result = await self.db.execute(query)
        rows = result.scalars().all()
        return {r.key: r.value for r in rows}

    async def set_value(self, key: str, value: Any, description: str = None) -> bool:
        """
        Crea o actualiza una configuración.
        """
        existing = await self.db.get(SystemSettingsModel, key)
        
        if existing:
            existing.value = value
            if description:
                existing.description = description
        else:
            new_setting = SystemSettingsModel(key=key, value=value, description=description)
            self.db.add(new_setting)
        
        await self.db.flush()
        logger.info(f"Configuración '{key}' actualizada a: {value}")
        return True
