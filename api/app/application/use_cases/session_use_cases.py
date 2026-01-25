"""
Casos de uso relacionados con sesiones de entrenamiento.
Contiene la logica de negocio para iniciar, gestionar y cerrar sesiones.
"""
from datetime import datetime
from loguru import logger

from app.application.dto.session_dto import SessionStartDTO, SessionResponseDTO
from app.shared.constants.session_constants import SessionStatus
from app.shared.exceptions.domain import InvalidAthleteException, SessionNotFoundException
from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.repositories.chat_repository import ChatRepository
from app.infrastructure.repositories.athlete_repository import AthleteRepository  # Import AthleteRepository
from sqlalchemy.ext.asyncio import AsyncSession


class SessionUseCases:
    """
    Casos de uso para gestion de sesiones de entrenamiento.
    Maneja la validacion de atletas y el ciclo de vida del driver.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ChatRepository(db)
        self.athlete_repo = AthleteRepository(db)  # Initialize AthleteRepository
    
    async def start_session(self, dto: SessionStartDTO) -> SessionResponseDTO:
        """
        Inicia una nueva sesion de entrenamiento para un atleta.
        
        Realiza el flujo completo:
        1. Valida que el atleta exista en la BD
        2. Abre el navegador en TrainingPeaks
        3. Hace login
        4. Selecciona el atleta en la plataforma
        5. Abre la Workout Library
        
        Args:
            dto: Datos de inicio de sesion con el nombre del atleta
            
        Returns:
            SessionResponseDTO: Informacion de la sesion iniciada
            
        Raises:
            InvalidAthleteException: Si el atleta no existe
        """
        # Validar atleta en DB
        athlete = None
        if dto.athlete_id:
            athlete = await self.athlete_repo.get_by_id(dto.athlete_id)
        
        # Fallback to name if ID not provided or lookup failed (though ID lookup shouldn't fail if valid)
        if not athlete:
            athlete = await self.athlete_repo.get_by_name(dto.athlete_name)
        
        if not athlete:
            logger.warning(f"Intento de inicio con atleta no encontrado: {dto.athlete_name} (ID: {dto.athlete_id})")
            # Use a generic message since we don't have a valid list to suggest
            raise InvalidAthleteException(
                athlete_name=dto.athlete_name,
                valid_athletes=[] 
            )
        
        # Construct full name manually as per user feedback that full_name field might be incomplete (just first name)
        # and last_name field contains the surnames.
        parts = []
        if athlete.name:
            parts.append(athlete.name.strip())
        if athlete.last_name:
            parts.append(athlete.last_name.strip())
        
        target_athlete_name = " ".join(parts).strip()
        
        # Fallback to name if result is empty (shouldn't happen if validation passed)
        if not target_athlete_name:
            target_athlete_name = athlete.name
        
        logger.info(f"Iniciando sesion para atleta valido: {target_athlete_name}")
        
        # Inicializar sesion completa de entrenamiento (version async para no bloquear)
        session = await DriverManager.initialize_training_session_async(target_athlete_name)
        
        # Retrieve athlete.id safely
        athlete_id = getattr(athlete, 'id', None)
        
        return SessionResponseDTO(
            session_id=session.session_id,
            athlete_name=session.athlete_name,
            athlete_id=athlete_id,
            status=SessionStatus.ACTIVE,
            driver_active=session.is_active,
            created_at=session.created_at,
            message=f"Sesion iniciada con Workout Library abierta para {target_athlete_name}"
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
        
        # Inicializar nuevo driver mantendo el ID (version async para no bloquear)
        driver_session = await DriverManager.initialize_training_session_async(
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

