"""
Endpoints de autenticación.

Este proyecto usa un login único configurado por env para habilitar acceso a la UI.
No se emiten tokens ni se protegen otros endpoints (enforcement UI-only).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.v1.dependencies.use_case_deps import get_auth_use_cases
from app.application.use_cases.auth_use_cases import AuthUseCases
from app.shared.exceptions.auth import InvalidCredentialsException
from app.shared.exceptions.base import AppException


class AuthLoginRequestDTO(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AuthLoginResponseDTO(BaseModel):
    ok: bool


class AuthNotConfiguredException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Auth no configurado (AUTH_USERNAME/AUTH_PASSWORD vacíos)",
            status_code=503,
            error_code="AUTH_NOT_CONFIGURED",
        )


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/login",
    response_model=AuthLoginResponseDTO,
    status_code=status.HTTP_200_OK,
    summary="Validar credenciales (login único)",
)
def login(
    dto: AuthLoginRequestDTO,
    use_cases: AuthUseCases = Depends(get_auth_use_cases),
) -> AuthLoginResponseDTO:
    if not use_cases.is_configured():
        raise AuthNotConfiguredException()

    if not use_cases.verify_login(dto.username, dto.password):
        raise InvalidCredentialsException()

    return AuthLoginResponseDTO(ok=True)


