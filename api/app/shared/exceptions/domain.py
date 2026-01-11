"""
Excepciones relacionadas con la lógica de dominio.
"""
from typing import Any

from app.shared.exceptions.base import AppException


class DomainException(AppException):
    """Excepción base para errores de dominio."""
    
    def __init__(self, message: str, error_code: str = "DOMAIN_ERROR", details=None):
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            details=details
        )


class EntityNotFoundException(DomainException):
    """Excepción cuando no se encuentra una entidad."""
    
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            message=f"{entity_name} con ID {entity_id} no encontrado",
            error_code="ENTITY_NOT_FOUND",
            details={"entity": entity_name, "id": str(entity_id)}
        )


class EntityAlreadyExistsException(DomainException):
    """Excepción cuando una entidad ya existe."""
    
    def __init__(self, entity_name: str, field: str, value: Any):
        super().__init__(
            message=f"{entity_name} con {field}={value} ya existe",
            error_code="ENTITY_ALREADY_EXISTS",
            details={"entity": entity_name, "field": field, "value": str(value)}
        )


class ValidationException(DomainException):
    """Excepción para errores de validación."""
    
    def __init__(self, message: str, field: str = None):
        details = {"field": field} if field else None
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details
        )


class InvalidAthleteException(DomainException):
    """Excepción cuando el atleta proporcionado no es válido."""
    
    def __init__(self, athlete_name: str, valid_athletes: list[str]):
        super().__init__(
            message=f"El atleta '{athlete_name}' no es válido",
            error_code="INVALID_ATHLETE",
            details={
                "athlete_provided": athlete_name,
                "valid_athletes": valid_athletes
            }
        )


class SessionNotFoundException(DomainException):
    """Excepcion cuando no se encuentra una sesion de entrenamiento o chat."""
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Sesion con ID '{session_id}' no encontrada",
            error_code="SESSION_NOT_FOUND",
            details={"session_id": session_id}
        )
        self.status_code = 404


class PlanNotFoundException(DomainException):
    """Excepcion cuando no se encuentra un plan de entrenamiento."""
    
    def __init__(self, plan_id: int):
        super().__init__(
            message=f"Plan con ID '{plan_id}' no encontrado",
            error_code="PLAN_NOT_FOUND",
            details={"plan_id": plan_id}
        )
        self.status_code = 404
