"""
Configuración central de la aplicación.
Gestiona variables de entorno y configuraciones globales.
"""
import json
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Clase de configuración de la aplicación.
    Lee variables de entorno y proporciona valores por defecto.
    """
    
    # Configuración de la aplicación
    APP_NAME: str = Field(default="Sistema de Agentes AutoGen")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="production")
    
    # Configuración del servidor
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    
    # Base de datos
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./app.db")
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)
    
    # Seguridad
    SECRET_KEY: str = Field(default="change-this-secret-key-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    
    # CORS (acepta lista JSON o "*" para todos los origenes)
    CORS_ORIGINS: str = Field(default="*")
    
    # AutoGen / LLM
    OPENAI_API_KEY: str = Field(default="")
    AUTOGEN_MODEL: str = Field(default="gpt-5-mini")
    AUTOGEN_TEMPERATURE: float = Field(default=0.7)
    AUTOGEN_MAX_TOKENS: int = Field(default=128000)
    
    # Workouts
    WORKOUTS_DIR: str = Field(default="workouts")
    DEFAULT_WORKOUT_LIBRARY: str = Field(default="AI Generated")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="logs/app.log")
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = Field(default=60)
    
    class Config:
        """Configuración de Pydantic."""
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

