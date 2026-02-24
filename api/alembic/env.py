"""
Configuracion de Alembic para migraciones de base de datos.

Este archivo configura Alembic para:
- Usar la URL de base de datos desde settings (config.py)
- Importar todos los modelos para autogenerate
- Soportar PostgreSQL (asyncpg se reemplaza por psycopg2 para migraciones sync)
"""
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Agregar el directorio raiz al path para imports
API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

# Importar configuracion y modelos
from app.core.config import settings
from app.infrastructure.database.session import Base

# Importar todos los modelos para que Alembic los detecte
from app.infrastructure.database.models import (
    AgentModel,
    ChatSessionModel,
    ConversationModel,
    TrainingModel,
    AthleteModel,
    TrainingPlanModel,
    SystemSettingsModel,
)

# Alembic Config object
config = context.config

# Configurar URL de base de datos desde settings
# Reemplazar asyncpg por psycopg (psycopg3) para migraciones sincronas
db_url = settings.effective_database_url.replace("+asyncpg", "+psycopg")
config.set_main_option("sqlalchemy.url", db_url)
# Configurar logging desde alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de los modelos para autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo 'offline'.
    
    Genera SQL sin conectarse a la base de datos.
    Util para revisar migraciones antes de ejecutarlas.
    """
    url = config.get_main_option("sqlalchemy.url")
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
    
    Conecta a la base de datos y ejecuta las migraciones directamente.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Comparar tipos de columnas para detectar cambios
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
