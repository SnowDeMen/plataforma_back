"""
Script para inicializar la base de datos.
"""
import asyncio
from loguru import logger

from sqlalchemy import text
from app.infrastructure.database.session import init_db, engine


async def main():
    """Función principal para inicializar la base de datos."""
    logger.info("Inicializando base de datos...")
    
    try:
        # Asegurar que el esquema 'airtable' exista antes de crear tablas
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS airtable"))
            
        await init_db()
        logger.success("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar base de datos: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

