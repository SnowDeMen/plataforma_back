"""
Utilidades para manejo de fechas y horas.
"""
from datetime import datetime, timezone
from typing import Optional


class DateTimeUtils:
    """Clase de utilidades para operaciones con fechas y horas."""
    
    @staticmethod
    def now_utc() -> datetime:
        """
        Obtiene la fecha y hora actual en UTC.
        
        Returns:
            datetime: Fecha y hora actual en UTC
        """
        return datetime.now(timezone.utc)
    
    @staticmethod
    def to_iso_string(dt: datetime) -> str:
        """
        Convierte un datetime a string ISO 8601.
        
        Args:
            dt: Objeto datetime
            
        Returns:
            str: Fecha en formato ISO 8601
        """
        return dt.isoformat()
    
    @staticmethod
    def from_iso_string(iso_string: str) -> Optional[datetime]:
        """
        Convierte un string ISO 8601 a datetime.
        
        Args:
            iso_string: String en formato ISO 8601
            
        Returns:
            Optional[datetime]: Objeto datetime o None si hay error
        """
        try:
            return datetime.fromisoformat(iso_string)
        except (ValueError, TypeError):
            return None

