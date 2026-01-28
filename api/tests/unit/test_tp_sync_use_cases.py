"""
Tests unitarios para TPSyncUseCases.

Estos tests verifican la logica del patron asincrono con jobs en memoria,
mockeando las dependencias externas (Selenium, DB, Airtable).
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from app.application.use_cases.tp_sync_use_cases import TPSyncUseCases, _JobState


class TestTPSyncUseCases:
    """Tests para la clase TPSyncUseCases."""
    
    @pytest.fixture
    def use_cases(self):
        """Crea una instancia limpia de TPSyncUseCases para cada test."""
        # Limpiar jobs de tests anteriores
        TPSyncUseCases._jobs = {}
        return TPSyncUseCases()
    
    # =========================================================================
    # Tests para start_sync
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_start_sync_returns_job_response(self, use_cases):
        """Verifica que start_sync retorna una respuesta con job_id."""
        with patch.object(use_cases, '_run_job', new_callable=AsyncMock) as mock_run:
            response = await use_cases.start_sync(
                username="test_user",
                athlete_id="rec123"
            )
            
            assert response.job_id is not None
            assert len(response.job_id) == 36  # UUID format
            assert response.status == "running"
            assert response.progress == 0
            assert "Iniciando" in response.message
            assert response.created_at is not None
    
    @pytest.mark.asyncio
    async def test_start_sync_creates_job_in_memory(self, use_cases):
        """Verifica que el job se guarda en el diccionario interno."""
        with patch.object(use_cases, '_run_job', new_callable=AsyncMock):
            response = await use_cases.start_sync(
                username="test_user",
                athlete_id="rec123"
            )
            
            assert response.job_id in TPSyncUseCases._jobs
            job = TPSyncUseCases._jobs[response.job_id]
            assert job.username == "test_user"
            assert job.athlete_id == "rec123"
            assert job.status == "running"
    
    @pytest.mark.asyncio
    async def test_start_sync_launches_background_task(self, use_cases):
        """Verifica que se lanza asyncio.create_task para el job."""
        with patch('asyncio.create_task') as mock_create_task:
            with patch.object(use_cases, '_run_job', new_callable=AsyncMock) as mock_run:
                await use_cases.start_sync(
                    username="test_user",
                    athlete_id="rec123"
                )
                
                # create_task deberia haberse llamado
                mock_create_task.assert_called_once()
    
    # =========================================================================
    # Tests para get_job_status
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_get_job_status_returns_current_state(self, use_cases):
        """Verifica que get_job_status retorna el estado actual del job."""
        # Crear un job manualmente
        job_id = "test-job-123"
        now = datetime.now(timezone.utc)
        TPSyncUseCases._jobs[job_id] = _JobState(
            job_id=job_id,
            username="test_user",
            athlete_id="rec123",
            status="running",
            progress=50,
            message="Buscando atleta...",
            created_at=now,
            updated_at=now,
        )
        
        status = await use_cases.get_job_status(job_id)
        
        assert status.job_id == job_id
        assert status.status == "running"
        assert status.progress == 50
        assert status.message == "Buscando atleta..."
    
    @pytest.mark.asyncio
    async def test_get_job_status_raises_keyerror_for_unknown_job(self, use_cases):
        """Verifica que lanza KeyError si el job no existe."""
        with pytest.raises(KeyError, match="job_not_found"):
            await use_cases.get_job_status("nonexistent-job")
    
    @pytest.mark.asyncio
    async def test_get_job_status_includes_result_when_completed(self, use_cases):
        """Verifica que el status incluye tp_name y group cuando completed."""
        job_id = "test-job-completed"
        now = datetime.now(timezone.utc)
        TPSyncUseCases._jobs[job_id] = _JobState(
            job_id=job_id,
            username="test_user",
            athlete_id="rec123",
            status="completed",
            progress=100,
            message="Sincronizado exitosamente",
            created_at=now,
            updated_at=now,
            completed_at=now,
            tp_name="Juan Perez",
            group="Grupo A",
        )
        
        status = await use_cases.get_job_status(job_id)
        
        assert status.status == "completed"
        assert status.tp_name == "Juan Perez"
        assert status.group == "Grupo A"
        assert status.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_get_job_status_includes_error_when_failed(self, use_cases):
        """Verifica que el status incluye error cuando failed."""
        job_id = "test-job-failed"
        now = datetime.now(timezone.utc)
        TPSyncUseCases._jobs[job_id] = _JobState(
            job_id=job_id,
            username="test_user",
            athlete_id="rec123",
            status="failed",
            progress=100,
            message="Error durante sincronizacion",
            created_at=now,
            updated_at=now,
            completed_at=now,
            error="Atleta no encontrado en TrainingPeaks",
        )
        
        status = await use_cases.get_job_status(job_id)
        
        assert status.status == "failed"
        assert status.error == "Atleta no encontrado en TrainingPeaks"
    
    # =========================================================================
    # Tests para _update_job
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_update_job_modifies_fields(self, use_cases):
        """Verifica que _update_job actualiza los campos correctamente."""
        job_id = "test-job-update"
        now = datetime.now(timezone.utc)
        TPSyncUseCases._jobs[job_id] = _JobState(
            job_id=job_id,
            username="test_user",
            athlete_id="rec123",
            status="running",
            progress=0,
            message="Iniciando...",
            created_at=now,
            updated_at=now,
        )
        
        await use_cases._update_job(
            job_id,
            progress=50,
            message="Buscando atleta..."
        )
        
        job = TPSyncUseCases._jobs[job_id]
        assert job.progress == 50
        assert job.message == "Buscando atleta..."
        assert job.updated_at > now
    
    @pytest.mark.asyncio
    async def test_update_job_ignores_nonexistent_job(self, use_cases):
        """Verifica que _update_job no falla si el job no existe."""
        # No deberia lanzar excepcion
        await use_cases._update_job(
            "nonexistent-job",
            progress=50
        )
    
    # =========================================================================
    # Tests para _run_job (flujo completo mockeado)
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_run_job_success_flow(self, use_cases):
        """Verifica el flujo exitoso completo del job."""
        job_id = "test-job-success"
        now = datetime.now(timezone.utc)
        TPSyncUseCases._jobs[job_id] = _JobState(
            job_id=job_id,
            username="test_user",
            athlete_id="rec123",
            status="running",
            progress=0,
            message="Iniciando...",
            created_at=now,
            updated_at=now,
        )
        
        # Mock del driver y servicios
        mock_driver = Mock()
        mock_wait = Mock()
        
        # Mock para find_athlete_by_username
        search_result = {
            "found": True,
            "full_name": "Juan Perez",
            "group": "Grupo A",
            "username": "test_user"
        }
        
        # Mock del atleta en DB
        mock_athlete = Mock()
        mock_athlete.id = "rec123"
        
        with patch('app.application.use_cases.tp_sync_use_cases.run_selenium', new_callable=AsyncMock) as mock_run_selenium, \
             patch('app.application.use_cases.tp_sync_use_cases.DriverManager') as mock_dm, \
             patch('app.application.use_cases.tp_sync_use_cases.AuthService') as mock_auth_cls, \
             patch('app.application.use_cases.tp_sync_use_cases.AthleteService') as mock_athlete_cls, \
             patch('app.application.use_cases.tp_sync_use_cases.AsyncSessionLocal') as mock_session, \
             patch.object(use_cases, '_sync_airtable', new_callable=AsyncMock) as mock_airtable:
            
            # Configurar mocks
            mock_run_selenium.side_effect = [
                (mock_driver, mock_wait),  # _create_driver_for_home
                None,  # login_with_cookie
                None,  # navigate_to_home
                search_result,  # find_athlete_by_username
                None,  # driver.quit
            ]
            
            # Mock del contexto de sesion DB
            mock_db = AsyncMock()
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = mock_athlete
            mock_session.return_value.__aenter__.return_value = mock_db
            
            with patch('app.application.use_cases.tp_sync_use_cases.AthleteRepository') as mock_repo_cls:
                mock_repo_cls.return_value = mock_repo
                
                await use_cases._run_job(
                    job_id=job_id,
                    username="test_user",
                    athlete_id="rec123"
                )
        
        # Verificar estado final
        job = TPSyncUseCases._jobs[job_id]
        assert job.status == "completed"
        assert job.progress == 100
        assert job.tp_name == "Juan Perez"
        assert job.group == "Grupo A"
    
    @pytest.mark.asyncio
    async def test_run_job_athlete_not_found_in_tp(self, use_cases):
        """Verifica que el job falla si el atleta no se encuentra en TP."""
        job_id = "test-job-not-found"
        now = datetime.now(timezone.utc)
        TPSyncUseCases._jobs[job_id] = _JobState(
            job_id=job_id,
            username="test_user",
            athlete_id="rec123",
            status="running",
            progress=0,
            message="Iniciando...",
            created_at=now,
            updated_at=now,
        )
        
        mock_driver = Mock()
        mock_wait = Mock()
        
        # Atleta no encontrado
        search_result = {
            "found": False,
            "full_name": None,
            "group": None,
        }
        
        with patch('app.application.use_cases.tp_sync_use_cases.run_selenium', new_callable=AsyncMock) as mock_run_selenium, \
             patch('app.application.use_cases.tp_sync_use_cases.AuthService'), \
             patch('app.application.use_cases.tp_sync_use_cases.AthleteService'):
            
            mock_run_selenium.side_effect = [
                (mock_driver, mock_wait),  # _create_driver_for_home
                None,  # login_with_cookie
                None,  # navigate_to_home
                search_result,  # find_athlete_by_username
                None,  # driver.quit
            ]
            
            await use_cases._run_job(
                job_id=job_id,
                username="test_user",
                athlete_id="rec123"
            )
        
        job = TPSyncUseCases._jobs[job_id]
        assert job.status == "failed"
        assert "no encontrado" in job.error.lower()
    
    @pytest.mark.asyncio
    async def test_run_job_handles_selenium_exception(self, use_cases):
        """Verifica que el job maneja excepciones de Selenium correctamente."""
        job_id = "test-job-selenium-error"
        now = datetime.now(timezone.utc)
        TPSyncUseCases._jobs[job_id] = _JobState(
            job_id=job_id,
            username="test_user",
            athlete_id="rec123",
            status="running",
            progress=0,
            message="Iniciando...",
            created_at=now,
            updated_at=now,
        )
        
        with patch('app.application.use_cases.tp_sync_use_cases.run_selenium', new_callable=AsyncMock) as mock_run_selenium:
            mock_run_selenium.side_effect = Exception("Selenium timeout")
            
            await use_cases._run_job(
                job_id=job_id,
                username="test_user",
                athlete_id="rec123"
            )
        
        job = TPSyncUseCases._jobs[job_id]
        assert job.status == "failed"
        assert job.error == "Selenium timeout"


class TestTPSyncJobState:
    """Tests para la clase _JobState."""
    
    def test_job_state_creation(self):
        """Verifica que _JobState se crea correctamente."""
        now = datetime.now(timezone.utc)
        job = _JobState(
            job_id="test-123",
            username="test_user",
            athlete_id="rec123",
            status="running",
            progress=0,
            message="Iniciando...",
            created_at=now,
            updated_at=now,
        )
        
        assert job.job_id == "test-123"
        assert job.username == "test_user"
        assert job.athlete_id == "rec123"
        assert job.status == "running"
        assert job.progress == 0
        assert job.tp_name is None
        assert job.group is None
        assert job.error is None
        assert job.completed_at is None
