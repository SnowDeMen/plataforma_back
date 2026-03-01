"""
Tests unitarios para la funcionalidad de from_date en el historial de entrenamientos.

Verifica:
- Validación del DTO (retrocompatibilidad, fechas válidas, fechas futuras).
- Lógica de parada del loop en _run_job cuando se usa from_date.
- Que sin from_date el comportamiento sigue siendo por gap_days.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from app.application.dto.training_history_dto import TrainingHistorySyncRequestDTO


class TestTrainingHistorySyncRequestDTO:
    """Validación del DTO con el nuevo campo from_date."""

    def test_dto_accepts_from_date_none_by_default(self) -> None:
        """Retrocompatibilidad: el DTO funciona sin from_date."""
        dto = TrainingHistorySyncRequestDTO()

        assert dto.from_date is None
        assert dto.gap_days == 180
        assert dto.timeout == 12

    def test_dto_accepts_valid_from_date(self) -> None:
        """Acepta una fecha válida como from_date."""
        target = date(2025, 6, 1)
        dto = TrainingHistorySyncRequestDTO(from_date=target)

        assert dto.from_date == target

    def test_dto_accepts_from_date_as_iso_string(self) -> None:
        """Acepta from_date como string ISO 8601."""
        dto = TrainingHistorySyncRequestDTO(from_date="2025-06-01")  # type: ignore

        assert dto.from_date == date(2025, 6, 1)

    def test_dto_rejects_future_from_date(self) -> None:
        """Rechaza fechas futuras."""
        future = date.today() + timedelta(days=30)

        with pytest.raises(ValidationError, match="from_date no puede ser una fecha futura"):
            TrainingHistorySyncRequestDTO(from_date=future)

    def test_dto_accepts_today_as_from_date(self) -> None:
        """Hoy es un valor límite válido."""
        dto = TrainingHistorySyncRequestDTO(from_date=date.today())

        assert dto.from_date == date.today()

    def test_dto_preserves_gap_days_and_timeout_with_from_date(self) -> None:
        """from_date no altera los demás campos."""
        dto = TrainingHistorySyncRequestDTO(
            from_date=date(2025, 1, 1),
            gap_days=90,
            timeout=20,
        )

        assert dto.from_date == date(2025, 1, 1)
        assert dto.gap_days == 90
        assert dto.timeout == 20

    def test_dto_rejects_invalid_date_string(self) -> None:
        """Rechaza strings que no son fechas válidas."""
        with pytest.raises(ValidationError):
            TrainingHistorySyncRequestDTO(from_date="not-a-date")  # type: ignore


def _build_run_job_mocks(extracted_dates: list[str], workout_fn):
    """
    Construye un mock de run_selenium que maneja la secuencia de llamadas de _run_job:
    1. _create_driver -> (mock_driver, mock_wait)
    2. login_with_cookie -> None
    3. select_athlete -> None
    4..N. get_all_quickviews_on_date(iso, ...) -> workout_fn(iso)
    """
    mock_driver = Mock()
    mock_wait = Mock()
    call_idx = 0

    async def fake_run_selenium(fn, *args, **kwargs):
        nonlocal call_idx
        call_idx += 1

        # Primera llamada: crear driver
        if call_idx == 1:
            return (mock_driver, mock_wait)
        # Segunda: login
        if call_idx == 2:
            return None
        # Tercera: seleccionar atleta
        if call_idx == 3:
            return None
        # Resto: extracción de workouts por fecha
        iso = args[0] if args else None
        if iso and isinstance(iso, str) and len(iso) == 10:
            extracted_dates.append(iso)
            return workout_fn(iso)
        return []

    mock_athlete = Mock()
    mock_athlete.tp_name = "Test Athlete"
    mock_athlete.name = "Test"
    mock_athlete.performance = {}

    mock_repo = AsyncMock()
    mock_repo.get_by_id = AsyncMock(return_value=mock_athlete)
    mock_repo.update = AsyncMock()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.commit = AsyncMock()

    return fake_run_selenium, mock_session, mock_repo


class TestRunJobFromDateLogic:
    """
    Verifica la lógica de parada del loop en _run_job.

    Se mockean todas las dependencias externas (Selenium, DB, imports dinámicos)
    para aislar la lógica del loop.
    """

    @pytest.mark.asyncio
    async def test_run_job_stops_at_from_date(self) -> None:
        """El loop se detiene al llegar a from_date, sin ir más atrás."""
        from app.application.use_cases.training_history_use_cases import TrainingHistoryUseCases

        uc = TrainingHistoryUseCases()
        today = date.today()
        from_date = today - timedelta(days=3)
        dto = TrainingHistorySyncRequestDTO(from_date=from_date, timeout=3)

        extracted_dates: list[str] = []
        fake_run, mock_session, mock_repo = _build_run_job_mocks(
            extracted_dates,
            workout_fn=lambda _iso: [{"workout_bar": {"title": "Run"}}],
        )

        with patch("app.application.use_cases.training_history_use_cases.run_selenium", side_effect=fake_run), \
             patch("app.application.use_cases.training_history_use_cases.AsyncSessionLocal", return_value=mock_session), \
             patch("app.application.use_cases.training_history_use_cases.AthleteRepository", return_value=mock_repo), \
             patch("app.infrastructure.trainingpeaks.tp_domain.core.set_driver"), \
             patch("app.infrastructure.trainingpeaks.tp_domain.core.clear_driver"), \
             patch("app.infrastructure.trainingpeaks.tp_domain.calendar.workout_service.get_all_quickviews_on_date"):

            await uc._run_job(job_id="test-job", athlete_id="athlete-1", dto=dto)

        # Debe haber revisado exactamente 4 días: today, today-1, today-2, today-3 (from_date inclusive)
        assert len(extracted_dates) == 4
        assert extracted_dates[-1] == from_date.isoformat()

        for d in extracted_dates:
            assert date.fromisoformat(d) >= from_date

    @pytest.mark.asyncio
    async def test_run_job_uses_gap_days_when_no_from_date(self) -> None:
        """Sin from_date, el loop se detiene por gap_days."""
        from app.application.use_cases.training_history_use_cases import TrainingHistoryUseCases

        uc = TrainingHistoryUseCases()
        today = date.today()
        dto = TrainingHistorySyncRequestDTO(from_date=None, gap_days=3, timeout=3)

        extracted_dates: list[str] = []

        def workout_fn(iso: str):
            # Solo devolver workout en el primer día (today)
            if iso == today.isoformat():
                return [{"workout_bar": {"title": "Run"}}]
            return []

        fake_run, mock_session, mock_repo = _build_run_job_mocks(
            extracted_dates,
            workout_fn=workout_fn,
        )

        with patch("app.application.use_cases.training_history_use_cases.run_selenium", side_effect=fake_run), \
             patch("app.application.use_cases.training_history_use_cases.AsyncSessionLocal", return_value=mock_session), \
             patch("app.application.use_cases.training_history_use_cases.AthleteRepository", return_value=mock_repo), \
             patch("app.infrastructure.trainingpeaks.tp_domain.core.set_driver"), \
             patch("app.infrastructure.trainingpeaks.tp_domain.core.clear_driver"), \
             patch("app.infrastructure.trainingpeaks.tp_domain.calendar.workout_service.get_all_quickviews_on_date"):

            await uc._run_job(job_id="test-job-2", athlete_id="athlete-2", dto=dto)

        # 1 día con workout + 3 días vacíos (gap_days=3) = 4 llamadas
        assert len(extracted_dates) == 4

    @pytest.mark.asyncio
    async def test_run_job_from_date_ignores_gap_logic(self) -> None:
        """Con from_date, el loop NO se detiene por gap aunque haya días vacíos."""
        from app.application.use_cases.training_history_use_cases import TrainingHistoryUseCases

        uc = TrainingHistoryUseCases()
        today = date.today()
        from_date = today - timedelta(days=5)
        dto = TrainingHistorySyncRequestDTO(from_date=from_date, gap_days=2, timeout=3)

        extracted_dates: list[str] = []

        def workout_fn(iso: str):
            if iso == today.isoformat():
                return [{"workout_bar": {"title": "Run"}}]
            return []

        fake_run, mock_session, mock_repo = _build_run_job_mocks(
            extracted_dates,
            workout_fn=workout_fn,
        )

        with patch("app.application.use_cases.training_history_use_cases.run_selenium", side_effect=fake_run), \
             patch("app.application.use_cases.training_history_use_cases.AsyncSessionLocal", return_value=mock_session), \
             patch("app.application.use_cases.training_history_use_cases.AthleteRepository", return_value=mock_repo), \
             patch("app.infrastructure.trainingpeaks.tp_domain.core.set_driver"), \
             patch("app.infrastructure.trainingpeaks.tp_domain.core.clear_driver"), \
             patch("app.infrastructure.trainingpeaks.tp_domain.calendar.workout_service.get_all_quickviews_on_date"):

            await uc._run_job(job_id="test-job-3", athlete_id="athlete-3", dto=dto)

        # Debe haber revisado los 6 días completos (today hasta from_date inclusive)
        # a pesar de que gap_days=2 y solo hubo workout en 1 día.
        assert len(extracted_dates) == 6
