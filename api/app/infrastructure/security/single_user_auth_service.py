"""
Servicio de autenticación de 1 usuario (credenciales hard-coded por env).

IMPORTANTE:
- Este servicio solo valida credenciales.
- No emite tokens ni protege el resto de la API (enforcement UI-only).
"""

from __future__ import annotations

import hmac


class SingleUserAuthService:
    """
    Verifica credenciales contra un único usuario/contraseña esperados.

    Usa comparación en tiempo constante (hmac.compare_digest) para reducir leaks
    por timing.
    """

    def __init__(self, expected_username: str, expected_password: str) -> None:
        self._expected_username = expected_username or ""
        self._expected_password = expected_password or ""

    def is_configured(self) -> bool:
        return bool(self._expected_username and self._expected_password)

    def verify(self, username: str, password: str) -> bool:
        if not self.is_configured():
            return False

        # compare_digest requiere mismo tipo: str vs str (OK en py3)
        username_ok = hmac.compare_digest(username or "", self._expected_username)
        password_ok = hmac.compare_digest(password or "", self._expected_password)
        return bool(username_ok and password_ok)


