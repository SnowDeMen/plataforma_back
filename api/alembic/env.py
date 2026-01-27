"""
Configuracion del entorno de Alembic.
Carga la URL de base de datos desde variables de entorno.
"""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy import create_engine

from alembic import context

# Agregar el directorio raiz al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Configuracion de Alembic
config = context.config

# Configurar logging desde alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar modelos para autogenerate
from app.infrastructure.database.models import Base
target_metadata = Base.metadata


def get_url() -> str:
    """Obtiene la URL de la base de datos desde variables de entorno."""
    url = os.getenv("DATABASE_URL", "")
    # Convertir asyncpg a psycopg2 para migraciones sincronas
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    return url


def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo 'offline'.
    Genera SQL sin conectar a la base de datos.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Ejecuta migraciones en modo 'online'.
    Conecta a la base de datos y ejecuta las migraciones.
    """
    connectable = create_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
