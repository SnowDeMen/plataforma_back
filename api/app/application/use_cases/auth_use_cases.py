"""
Casos de uso para autenticación.

Caso principal en este proyecto:
- login único para habilitar acceso a la UI (frontend).
"""

from __future__ import annotations

from app.infrastructure.security.single_user_auth_service import SingleUserAuthService


class AuthUseCases:
    def __init__(self, auth_service: SingleUserAuthService) -> None:
        self._auth_service = auth_service

    def is_configured(self) -> bool:
        return self._auth_service.is_configured()

    def verify_login(self, username: str, password: str) -> bool:
        return self._auth_service.verify(username=username, password=password)


