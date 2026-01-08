"""
Script para inicializar la base de datos.
"""
import asyncio
from loguru import logger

# Importar modulos de database para registrar modelos con Base
from app.infrastructure import database  # noqa: F401
from app.infrastructure.database.session import init_db


async def main():
    """Función principal para inicializar la base de datos."""
    logger.info("Inicializando base de datos...")
    
    try:
        await init_db()
        logger.success("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar base de datos: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

