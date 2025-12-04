"""
Gestión de sesiones de base de datos.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings


# Base para modelos de SQLAlchemy
Base = declarative_base()


def _create_engine_args() -> dict:
    """
    Construye los argumentos del engine segun el tipo de base de datos.
    PostgreSQL usa pool de conexiones, SQLite no lo soporta.
    """
    args = {
        "echo": settings.DEBUG,
        "future": True,
    }
    
    # Configuracion de pool solo para PostgreSQL
    if "postgresql" in settings.DATABASE_URL:
        args.update({
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_pre_ping": True,  # Verifica conexion antes de usar
        })
    
    return args


# Engine de base de datos
engine = create_async_engine(settings.DATABASE_URL, **_create_engine_args())

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador de sesiones de base de datos.
    Para usar como dependencia en FastAPI.
    
    Yields:
        AsyncSession: Sesión de base de datos
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Inicializa la base de datos creando todas las tablas."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Cierra las conexiones de la base de datos."""
    await engine.dispose()

