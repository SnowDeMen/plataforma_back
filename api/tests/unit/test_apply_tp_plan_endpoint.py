"""
Tests unitarios para el endpoint apply-tp-plan.

Verifica la funcionalidad del endpoint que aplica Training Plans
de TrainingPeaks a atletas usando Selenium.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.application.dto.plan_dto import (
    ApplyTPPlanRequestDTO,
    ApplyTPPlanResponseDTO
)
from app.application.use_cases.plan_use_cases import PlanUseCases


class TestApplyTPPlanRequestDTO:
    """Tests para validacion del DTO de request."""

    def test_valid_request(self) -> None:
        """Verifica que un request valido se parsea correctamente."""
        dto = ApplyTPPlanRequestDTO(
            plan_name="Test Plan",
            athlete_name="Luis Aragon",
            start_date=date(2024, 9, 5)
        )
        
        assert dto.plan_name == "Test Plan"
        assert dto.athlete_name == "Luis Aragon"
        assert dto.start_date == date(2024, 9, 5)

    def test_request_requires_plan_name(self) -> None:
        """Verifica que plan_name es requerido."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ApplyTPPlanRequestDTO(
                plan_name="",  # Empty string should fail min_length
                athlete_name="Luis Aragon",
                start_date=date(2024, 9, 5)
            )

    def test_request_requires_athlete_name(self) -> None:
        """Verifica que athlete_name es requerido."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ApplyTPPlanRequestDTO(
                plan_name="Test",
                athlete_name="",  # Empty string should fail min_length
                start_date=date(2024, 9, 5)
            )

    def test_request_requires_start_date(self) -> None:
        """Verifica que start_date es requerido."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            ApplyTPPlanRequestDTO(
                plan_name="Test",
                athlete_name="Luis Aragon"
                # start_date missing
            )

    def test_start_date_accepts_iso_string(self) -> None:
        """Verifica que acepta fecha como string ISO 8601."""
        dto = ApplyTPPlanRequestDTO(
            plan_name="Test",
            athlete_name="Luis Aragon",
            start_date="2024-09-05"  # type: ignore
        )
        
        assert dto.start_date == date(2024, 9, 5)


class TestApplyTPPlanResponseDTO:
    """Tests para el DTO de response."""

    def test_success_response(self) -> None:
        """Verifica response exitoso."""
        dto = ApplyTPPlanResponseDTO(
            success=True,
            message="Plan aplicado exitosamente",
            plan_name="Test Plan",
            athlete_name="Luis Aragon",
            start_date="2024-09-05"
        )
        
        assert dto.success is True
        assert "exitosamente" in dto.message
        assert dto.plan_name == "Test Plan"

    def test_error_response(self) -> None:
        """Verifica response de error."""
        dto = ApplyTPPlanResponseDTO(
            success=False,
            message="Error: Timeout al hacer click",
            plan_name="Test Plan",
            athlete_name="Luis Aragon",
            start_date="2024-09-05"
        )
        
        assert dto.success is False
        assert "Error" in dto.message


class TestApplyTPPlanUseCase:
    """Tests para el use case apply_tp_plan."""

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Fixture que crea un mock de la sesion de BD."""
        return AsyncMock()

    @pytest.fixture
    def use_cases(self, mock_db: AsyncMock) -> PlanUseCases:
        """Fixture que crea instancia de PlanUseCases con mock."""
        return PlanUseCases(mock_db)

    @pytest.mark.asyncio
    async def test_apply_tp_plan_success(self, use_cases: PlanUseCases) -> None:
        """Verifica flujo exitoso de aplicar TP Plan."""
        dto = ApplyTPPlanRequestDTO(
            plan_name="Test",
            athlete_name="Luis Aragon",
            start_date=date(2024, 9, 5)
        )
        
        # Mock del DriverManager y servicios
        mock_session = Mock()
        mock_session.session_id = "test-session-id"
        mock_session.auth_service = Mock()
        mock_session.auth_service.login_with_cookie = Mock()
        mock_session.workout_service = Mock()
        mock_session.workout_service.workout_library = Mock()
        mock_session.training_plan_service = Mock()
        mock_session.training_plan_service.apply_training_plan = Mock()
        
        with patch('app.infrastructure.driver.selenium_executor.run_selenium') as mock_run_selenium, \
             patch('app.infrastructure.driver.driver_manager.DriverManager') as mock_driver_manager:
            
            # Configurar mocks
            mock_driver_manager.create_session = Mock(return_value=mock_session)
            mock_driver_manager.close_session = Mock()
            
            # run_selenium retorna el valor de la funcion pasada
            async def mock_run_selenium_impl(func, *args, **kwargs):
                if callable(func):
                    return func(*args, **kwargs)
                return mock_session
            
            mock_run_selenium.side_effect = mock_run_selenium_impl
            
            result = await use_cases.apply_tp_plan(dto)
            
            assert result.success is True
            assert "exitosamente" in result.message
            assert result.plan_name == "Test"
            assert result.athlete_name == "Luis Aragon"

    @pytest.mark.asyncio
    async def test_apply_tp_plan_selenium_error(self, use_cases: PlanUseCases) -> None:
        """Verifica manejo de error de Selenium."""
        dto = ApplyTPPlanRequestDTO(
            plan_name="Test",
            athlete_name="Luis Aragon",
            start_date=date(2024, 9, 5)
        )
        
        with patch('app.infrastructure.driver.selenium_executor.run_selenium') as mock_run_selenium, \
             patch('app.infrastructure.driver.driver_manager.DriverManager') as mock_driver_manager:
            
            # Simular error en Selenium
            mock_run_selenium.side_effect = Exception("Timeout al hacer click")
            
            result = await use_cases.apply_tp_plan(dto)
            
            assert result.success is False
            assert "Error" in result.message
            assert "Timeout" in result.message

    @pytest.mark.asyncio
    async def test_apply_tp_plan_closes_session_on_error(self, use_cases: PlanUseCases) -> None:
        """Verifica que la sesion se cierra incluso si hay error."""
        dto = ApplyTPPlanRequestDTO(
            plan_name="Test",
            athlete_name="Luis Aragon",
            start_date=date(2024, 9, 5)
        )
        
        mock_session = Mock()
        mock_session.session_id = "test-session-id"
        
        call_count = 0
        
        with patch('app.infrastructure.driver.selenium_executor.run_selenium') as mock_run_selenium, \
             patch('app.infrastructure.driver.driver_manager.DriverManager') as mock_driver_manager:
            
            async def mock_run_selenium_impl(func, *args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Primera llamada: crear sesion
                    return mock_session
                else:
                    # Siguientes llamadas: error
                    raise Exception("Error de Selenium")
            
            mock_run_selenium.side_effect = mock_run_selenium_impl
            mock_driver_manager.close_session = Mock()
            
            result = await use_cases.apply_tp_plan(dto)
            
            # Debe cerrar la sesion aunque haya error
            mock_driver_manager.close_session.assert_called_once_with("test-session-id")
            assert result.success is False


class TestDateFormatInResponse:
    """Tests para verificar formato de fecha en response."""

    def test_date_format_is_iso(self) -> None:
        """Verifica que la fecha en response es ISO 8601."""
        dto = ApplyTPPlanResponseDTO(
            success=True,
            message="OK",
            plan_name="Test",
            athlete_name="Luis",
            start_date="2024-09-05"
        )
        
        assert dto.start_date == "2024-09-05"
        # Verificar que es parseable
        parsed = date.fromisoformat(dto.start_date)
        assert parsed == date(2024, 9, 5)
