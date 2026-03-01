"""
Tests unitarios para el endpoint de sincronización de historial de entrenamientos.

Verifica el contrato HTTP:
- Acepta from_date como parámetro opcional.
- Funciona sin from_date (retrocompatibilidad).
- Rechaza formatos de fecha inválidos con 422.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.application.dto.training_history_dto import TrainingHistorySyncResponseDTO
from app.api.v1.dependencies.use_case_deps import get_training_history_use_cases


def _mock_sync_response() -> TrainingHistorySyncResponseDTO:
    return TrainingHistorySyncResponseDTO(
        job_id="fake-job-id",
        status="running",
        progress=0,
        message="Iniciando...",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_use_cases() -> AsyncMock:
    uc = AsyncMock()
    uc.start_sync = AsyncMock(return_value=_mock_sync_response())
    return uc


@pytest.fixture
def app_with_mock(mock_use_cases: AsyncMock):
    """Crea la app FastAPI con el use case mockeado via dependency_overrides."""
    from main import create_application
    app = create_application()
    app.dependency_overrides[get_training_history_use_cases] = lambda: mock_use_cases
    yield app
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sync_endpoint_accepts_from_date(app_with_mock, mock_use_cases: AsyncMock) -> None:
    """POST con from_date válido retorna 202."""
    transport = ASGITransport(app=app_with_mock)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/athletes/athlete-1/training-history/sync",
            json={"from_date": "2025-06-01"},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "fake-job-id"
    assert data["status"] == "running"

    call_args = mock_use_cases.start_sync.call_args
    dto = call_args.kwargs.get("dto") or call_args[1].get("dto") or call_args[0][1]
    assert dto.from_date == date(2025, 6, 1)


@pytest.mark.asyncio
async def test_sync_endpoint_works_without_from_date(app_with_mock, mock_use_cases: AsyncMock) -> None:
    """POST sin from_date retorna 202 (retrocompatibilidad)."""
    transport = ASGITransport(app=app_with_mock)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/athletes/athlete-1/training-history/sync",
            json={},
        )

    assert response.status_code == 202

    call_args = mock_use_cases.start_sync.call_args
    dto = call_args.kwargs.get("dto") or call_args[1].get("dto") or call_args[0][1]
    assert dto.from_date is None


@pytest.mark.asyncio
async def test_sync_endpoint_rejects_invalid_date_format(app_with_mock, mock_use_cases: AsyncMock) -> None:
    """POST con from_date inválido retorna 422."""
    transport = ASGITransport(app=app_with_mock)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/athletes/athlete-1/training-history/sync",
            json={"from_date": "not-a-date"},
        )

    assert response.status_code == 422
