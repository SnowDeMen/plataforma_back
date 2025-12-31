"""
Configuracion central de la aplicacion.
Gestiona variables de entorno y configuraciones globales.
Soporta configuracion dinamica para desarrollo (ENVIRONMENT=development)
y produccion (ENVIRONMENT=production).
"""
import json
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


class Settings(BaseSettings):
    """
    Clase de configuracion de la aplicacion.
    Lee variables de entorno y proporciona valores por defecto.
    
    Configuracion de desarrollo vs produccion:
    - ENVIRONMENT: 'development' o 'production'
    - En desarrollo: SELENIUM_HEADLESS=false para ver el navegador
    - En produccion: SELENIUM_HEADLESS=true (headless)
    - DATABASE_URL se puede especificar completa o por componentes
    """
    
    # Configuracion de la aplicacion
    APP_NAME: str = Field(default="Sistema de Agentes AutoGen")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")
    
    # Configuracion del servidor
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    
    # Base de datos - Componentes separados (recomendado para flexibilidad)
    DATABASE_HOST: str = Field(default="localhost")
    DATABASE_PORT: int = Field(default=5432)
    DATABASE_USER: str = Field(default="training_user")
    DATABASE_PASSWORD: str = Field(default="training_pass")
    DATABASE_NAME: str = Field(default="training_db")
    
    # Base de datos - URL completa (override de componentes si se proporciona)
    DATABASE_URL: str = Field(default="")
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)
    
    # Selenium - Configurable para desarrollo (ver navegador) vs produccion (headless)
    SELENIUM_HEADLESS: bool = Field(default=True)
    
    # Seguridad
    SECRET_KEY: str = Field(default="change-this-secret-key-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    
    # CORS (acepta lista JSON o "*" para todos los origenes)
    CORS_ORIGINS: str = Field(default="*")
    
    # AutoGen / LLM
    OPENAI_API_KEY: str = Field(default="")
    # Modelo default "seguro": se puede sobreescribir por variable de entorno AUTOGEN_MODEL.
    # Nota: si se usa un modelo no disponible en la cuenta, OpenAI puede responder 404/400.
    AUTOGEN_MODEL: str = Field(default="gpt-4o-mini")
    AUTOGEN_TEMPERATURE: float = Field(default=0.7)
    AUTOGEN_MAX_TOKENS: int = Field(default=128000)
    
    # Workouts
    WORKOUTS_DIR: str = Field(default="workouts")
    DEFAULT_WORKOUT_LIBRARY: str = Field(default="Neuronomy")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="logs/app.log")
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    
    @computed_field
    @property
    def effective_database_url(self) -> str:
        """
        Retorna la URL de base de datos efectiva.
        Si DATABASE_URL esta definida, la usa directamente.
        Si no, construye la URL desde los componentes individuales.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )
    
    @computed_field
    @property
    def is_development(self) -> bool:
        """Indica si el entorno es de desarrollo."""
        return self.ENVIRONMENT.lower() == "development"
    
    class Config:
        """Configuracion de Pydantic."""
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignorar campos extra del .env


def get_cors_origins(cors_string: str) -> List[str]:
    """
    Parsea la configuracion de CORS.
    Acepta "*" para todos los origenes o una lista JSON.
    """
    if cors_string == "*":
        return ["*"]
    try:
        return json.loads(cors_string)
    except json.JSONDecodeError:
        # Si no es JSON valido, retornar como lista simple
        return [origin.strip() for origin in cors_string.split(",")]


# Instancia global de configuración
settings = Settings()

