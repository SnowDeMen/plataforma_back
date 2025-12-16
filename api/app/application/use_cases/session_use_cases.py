"""
Casos de uso relacionados con sesiones de entrenamiento.
Contiene la logica de negocio para iniciar, gestionar y cerrar sesiones.
"""
from datetime import datetime
from loguru import logger

from app.application.dto.session_dto import SessionStartDTO, SessionResponseDTO
from app.shared.constants.session_constants import (
    SessionStatus, 
    VALID_ATHLETES, 
    is_valid_athlete
)
from app.shared.exceptions.domain import InvalidAthleteException, SessionNotFoundException
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.repositories.chat_repository import ChatRepository
from sqlalchemy.ext.asyncio import AsyncSession


class SessionUseCases:
    """
    Casos de uso para gestion de sesiones de entrenamiento.
    Maneja la validacion de atletas y el ciclo de vida del driver.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ChatRepository(db)
    
    def start_session(self, dto: SessionStartDTO) -> SessionResponseDTO:
        """
        Inicia una nueva sesion de entrenamiento para un atleta.
        
        Realiza el flujo completo:
        1. Valida que el atleta sea uno de los permitidos
        2. Abre el navegador en TrainingPeaks
        3. Hace login
        4. Selecciona el atleta en la plataforma
        5. Abre la Workout Library
        
        Args:
            dto: Datos de inicio de sesion con el nombre del atleta
            
        Returns:
            SessionResponseDTO: Informacion de la sesion iniciada
            
        Raises:
            InvalidAthleteException: Si el atleta no es valido
        """
        # Validar atleta
        if not is_valid_athlete(dto.athlete_name):
            logger.warning(f"Intento de inicio con atleta invalido: {dto.athlete_name}")
            raise InvalidAthleteException(
                athlete_name=dto.athlete_name,
                valid_athletes=VALID_ATHLETES
            )
        
        logger.info(f"Iniciando sesion para atleta valido: {dto.athlete_name}")
        
        # Inicializar sesion completa de entrenamiento
        session = DriverManager.initialize_training_session(dto.athlete_name)
        
        return SessionResponseDTO(
            session_id=session.session_id,
            athlete_name=session.athlete_name,
            status=SessionStatus.ACTIVE,
            driver_active=session.is_active,
            created_at=session.created_at,
            message=f"Sesion iniciada con Workout Library abierta para {dto.athlete_name}"
        )
    
    def get_session_status(self, session_id: str) -> SessionResponseDTO:
        """
        Obtiene el estado actual de una sesion.
        
        Args:
            session_id: ID de la sesion a consultar
            
        Returns:
            SessionResponseDTO: Estado actual de la sesion
            
        Raises:
            Exception: Si la sesion no existe
        """
        session = DriverManager.get_session(session_id)
        
        if not session:
            raise Exception(f"Sesion {session_id} no encontrada")
        
        is_active = DriverManager.is_session_active(session_id)
        status = SessionStatus.ACTIVE if is_active else SessionStatus.ERROR
        
        return SessionResponseDTO(
            session_id=session.session_id,
            athlete_name=session.athlete_name,
            status=status,
            driver_active=is_active,
            created_at=session.created_at,
            message=None
        )
    
    def close_session(self, session_id: str) -> bool:
        """
        Cierra una sesion y libera sus recursos.
        
        Args:
            session_id: ID de la sesion a cerrar
            
        Returns:
            bool: True si se cerro correctamente
        """
        result = DriverManager.close_session(session_id)
        if result:
            logger.info(f"Sesion {session_id} cerrada exitosamente")
        else:
            logger.warning(f"Sesion {session_id} no encontrada para cerrar")
        return result

    async def restart_session(self, session_id: str) -> SessionResponseDTO:
        """
        Reinicia el driver de Selenium para una sesion existente.
        
        Args:
            session_id: ID de la sesion a reiniciar
            
        Returns:
            SessionResponseDTO: Estado de la sesion reiniciada
            
        Raises:
            SessionNotFoundException: Si la sesion no existe
        """
        # Obtener sesion de base de datos para saber el atleta
        session = await self.repository.get_by_session_id(session_id)
        
        if not session:
            raise SessionNotFoundException(session_id)
            
        logger.info(f"Reiniciando driver para sesion {session_id} (Atleta: {session.athlete_name})")
        
        # Cerrar driver anterior si existe
        DriverManager.close_session(session_id)
        
        # Inicializar nuevo driver mantendo el ID
        driver_session = DriverManager.initialize_training_session(
            athlete_name=session.athlete_name, 
            session_id=session_id
        )
        
        return SessionResponseDTO(
            session_id=driver_session.session_id,
            athlete_name=driver_session.athlete_name,
            status=SessionStatus.ACTIVE,
            driver_active=driver_session.is_active,
            created_at=driver_session.created_at,
            message=f"Driver reiniciado para {session.athlete_name}"
        )

