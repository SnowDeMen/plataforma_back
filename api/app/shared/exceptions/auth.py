"""
Excepciones relacionadas con autenticación y autorización.
"""
from app.shared.exceptions.base import AppException


class AuthException(AppException):
    """Excepción base para errores de autenticación."""
    
    def __init__(self, message: str, error_code: str = "AUTH_ERROR", details=None):
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
            details=details
        )


class InvalidCredentialsException(AuthException):
    """Excepción para credenciales inválidas."""
    
    def __init__(self):
        super().__init__(
            message="Credenciales inválidas",
            error_code="INVALID_CREDENTIALS"
        )


class TokenExpiredException(AuthException):
    """Excepción para token expirado."""
    
    def __init__(self):
        super().__init__(
            message="El token ha expirado",
            error_code="TOKEN_EXPIRED"
        )


class UnauthorizedException(AuthException):
    """Excepción para acceso no autorizado."""
    
    def __init__(self, message: str = "No autorizado"):
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED"
        )


class ForbiddenException(AppException):
    """Excepción para acceso prohibido."""
    
    def __init__(self, message: str = "Acceso prohibido"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN"
        )

