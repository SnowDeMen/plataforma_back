"""
Configuración de fixtures para pytest.
"""
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.infrastructure.database.session import Base


# URL de base de datos de prueba
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Crea un event loop para toda la sesión de tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture que proporciona una sesión de base de datos para tests.
    Crea una base de datos en memoria para cada test.
    """
    # Crear engine de prueba
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Crear tablas
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Crear session factory
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Proporcionar sesión
    async with async_session() as session:
        yield session
    
    # Limpiar
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

