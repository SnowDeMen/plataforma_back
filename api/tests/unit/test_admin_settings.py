import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch
from app.application.use_cases.admin_use_cases import AdminUseCases

@pytest_asyncio.fixture
async def mock_db_session():
    return AsyncMock(spec=AsyncSession)

@pytest.mark.asyncio
async def test_update_days_in_advance_generation_success(mock_db_session):
    use_cases = AdminUseCases(mock_db_session)
    use_cases.settings_repo = AsyncMock()
    use_cases.settings_repo.set_value = AsyncMock(return_value=True)

    result = await use_cases.update_days_in_advance_generation(5)
    
    assert result is True
    use_cases.settings_repo.set_value.assert_called_once_with(
        "days_in_advance_generation", 
        5,
        "Días de anticipación para generar automáticamente el nuevo plan (basado en plan_end_date)."
    )
    mock_db_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_update_days_in_advance_generation_invalid(mock_db_session):
    use_cases = AdminUseCases(mock_db_session)
    use_cases.settings_repo = AsyncMock()

    result = await use_cases.update_days_in_advance_generation(-1)
    
    assert result is False
    use_cases.settings_repo.set_value.assert_not_called()
    mock_db_session.commit.assert_not_called()

@pytest.mark.asyncio
async def test_seed_default_settings(mock_db_session):
    use_cases = AdminUseCases(mock_db_session)
    use_cases.settings_repo = AsyncMock()
    # Mock get_value to return None for both calls, simulating empty settings
    use_cases.settings_repo.get_value = AsyncMock(return_value=None)
    
    await use_cases.seed_default_settings()
    
    # Should be called twice (one for telegram interval, one for days in advance)
    assert use_cases.settings_repo.get_value.call_count == 2
    assert use_cases.settings_repo.set_value.call_count == 2
    
    # Check that it saves days_in_advance_generation with default 3
    calls = use_cases.settings_repo.set_value.call_args_list
    days_advance_call = [c for c in calls if c[0][0] == "days_in_advance_generation"][0]
    assert days_advance_call[0][1] == 3
    
    mock_db_session.commit.assert_called_once()
