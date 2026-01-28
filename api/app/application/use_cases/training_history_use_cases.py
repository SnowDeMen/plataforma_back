"""
Casos de uso para sincronizar el historial de entrenamientos desde TrainingPeaks.

Características clave:
- Flujo separado del chat (endpoint dedicado).
- Reutiliza la sesión Selenium existente (`session_id`) y el MCP.
- Serializa acceso al driver por sesión mediante lock.
- Persiste resultado como JSON dentro de `AthleteModel.performance`.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from app.application.dto.training_history_dto import (
    TrainingHistoryJobStatusDTO,
    TrainingHistorySyncRequestDTO,
    TrainingHistorySyncResponseDTO,
)
from app.application.use_cases.training_history_policy import (
    should_stop_after_gap,
    sort_day_keys_ascending,
)
from app.core.config import settings
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.driver.driver_manager import TRAININGPEAKS_URL
from app.infrastructure.driver.selenium_executor import run_selenium
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService
from app.infrastructure.repositories.athlete_repository import AthleteRepository
from app.application.use_cases.training_history_limits import enforce_workout_limits


@dataclass
class _JobState:
    job_id: str
    session_id: str
    athlete_id: str
    status: str
    progress: int
    message: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class TrainingHistoryUseCases:
    """
    Orquestador de jobs de sincronización.

    Nota: los jobs se guardan en memoria (dict). Para el caso de uso actual es suficiente:
    - Permite polling simple desde el frontend.
    - No introduce infraestructura extra.
    """

    _jobs: Dict[str, _JobState] = {}
    _jobs_lock = asyncio.Lock()

    async def start_sync(self, athlete_id: str, dto: TrainingHistorySyncRequestDTO) -> TrainingHistorySyncResponseDTO:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        job = _JobState(
            job_id=job_id,
            session_id="",
            athlete_id=athlete_id,
            status="running",
            progress=0,
            message="Iniciando extracción de historial...",
            created_at=now,
            updated_at=now,
        )

        async with self._jobs_lock:
            self._jobs[job_id] = job

        # Ejecutar en background sin bloquear la request.
        asyncio.create_task(self._run_job(job_id=job_id, athlete_id=athlete_id, dto=dto))

        return TrainingHistorySyncResponseDTO(
            job_id=job_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            created_at=job.created_at,
        )

    async def get_job_status(self, athlete_id: str, job_id: str) -> TrainingHistoryJobStatusDTO:
        async with self._jobs_lock:
            job = self._jobs.get(job_id)

        if job is None or job.athlete_id != athlete_id:
            # No filtramos detalles para no filtrar existencia entre sesiones.
            raise KeyError("job_not_found")

        return TrainingHistoryJobStatusDTO(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            error=job.error,
        )

    async def _update_job(self, job_id: str, **changes: Any) -> None:
        async with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for k, v in changes.items():
                setattr(job, k, v)
            job.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _find_mcp_domain_path() -> Path:
        """
        Encuentra la carpeta `plataforma_back/mcp` para poder importar `domain.*`
        (navegación/extracción) sin depender del servidor MCP.
        """
        current = Path(__file__).resolve()
        for _ in range(10):
            current = current.parent
            candidate = current / "plataforma_back" / "mcp"
            if candidate.exists() and (candidate / "domain").exists():
                return candidate
        # Fallback: estructura esperada cuando se ejecuta dentro de plataforma_back/api
        # (subimos hasta encontrar `mcp/` directamente)
        current = Path(__file__).resolve()
        for _ in range(10):
            current = current.parent
            candidate = current / "mcp"
            if candidate.exists() and (candidate / "domain").exists():
                return candidate
        raise RuntimeError("No se encontró el path de `mcp/domain` para reutilizar funciones de calendario.")

    @classmethod
    def _ensure_domain_imports(cls) -> None:
        mcp_path = cls._find_mcp_domain_path()
        mcp_path_str = str(mcp_path)
        if mcp_path_str not in sys.path:
            sys.path.insert(0, mcp_path_str)

    @staticmethod
    def _create_driver() -> tuple[webdriver.Chrome, WebDriverWait]:
        """
        Crea un driver dedicado para el job de historial.

        Nota: se alinea con la configuración usada por `DriverManager`,
        pero este driver no se registra como sesión global.
        """
        opts = Options()
        if settings.SELENIUM_HEADLESS:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--remote-debugging-port=9222")

        driver = webdriver.Chrome(options=opts)
        wait = WebDriverWait(driver, 10)
        driver.get(TRAININGPEAKS_URL)
        return driver, wait

    async def _run_job(self, *, job_id: str, athlete_id: str, dto: TrainingHistorySyncRequestDTO) -> None:
        """
        Ejecuta la extracción hacia atrás con criterio stop_after_gap y persiste en DB.

        Implementación:
        - Itera día a día hacia atrás.
        - Usa `obtener_datos_calendario` (MCP) con `use_today` solo en la primera llamada
          para acelerar el barrido.
        - Corta cuando hay `gap_days` sin entrenos luego de haber encontrado al menos uno.
        
        Nota: Las operaciones de Selenium se ejecutan en threads separados via run_selenium()
        para no bloquear el event loop y permitir que el healthcheck responda.
        """
        try:
            await self._update_job(job_id, message="Preparando sesión Selenium/MCP...", progress=0, status="running")
            # Obtener nombre del atleta para selección en TrainingPeaks.
            async with AsyncSessionLocal() as db_lookup:
                repo = AthleteRepository(db_lookup)
                athlete = await repo.get_by_id(athlete_id)
                if athlete is None:
                    raise RuntimeError(f"Atleta no encontrado en DB: {athlete_id}")
                athlete_name = athlete.name

            await self._update_job(job_id, message="Creando driver dedicado y autenticando...", progress=1)

            self._ensure_domain_imports()
            from domain.core import set_driver, clear_driver  # type: ignore
            from domain.calendar.workout_service import get_all_quickviews_on_date  # type: ignore

            driver: Optional[webdriver.Chrome] = None
            wait: Optional[WebDriverWait] = None
            try:
                # Crear driver en thread separado para no bloquear el event loop
                driver, wait = await run_selenium(self._create_driver)

                # Login + selección de atleta en threads separados
                await run_selenium(AuthService(driver, wait).login_with_cookie)
                await run_selenium(AthleteService(driver, wait).select_athlete, athlete_name)

                # Inyectar driver para reutilizar funciones del dominio (calendar).
                set_driver(driver, wait)

                today = date.today()
                cursor = today
                first_call = True

                has_found_any = False
                consecutive_empty = 0
                checked_days = 0
                error_days = 0

                max_days = 365 * 25
                days: Dict[str, Any] = {}

                while checked_days < max_days:
                    iso = cursor.isoformat()

                    if checked_days % 7 == 0:
                        await self._update_job(
                            job_id,
                            message=f"Extrayendo... fecha {iso} (días revisados: {checked_days})",
                            progress=min(95, int((checked_days / max_days) * 100)),
                        )

                    try:
                        # Ejecutar extraccion en thread para no bloquear el event loop
                        workouts_for_day = await run_selenium(
                            get_all_quickviews_on_date,
                            iso,
                            use_today=True if first_call else False,
                            timeout=dto.timeout,
                            limit=None,
                        )
                    except Exception as e:
                        error_days += 1
                        workouts_for_day = []
                        logger.warning(f"Historial: error extrayendo {iso}: {e}")
                    finally:
                        first_call = False

                    # Aplicar límites por workout para evitar payloads excesivos (HTML/texto).
                    if workouts_for_day:
                        limited_day: list[dict] = []
                        for w in workouts_for_day:
                            if isinstance(w, dict):
                                limited, _ = enforce_workout_limits(w)
                                limited_day.append(limited)
                            else:
                                # Si por alguna razón viene un tipo inesperado, lo preservamos como dict mínimo.
                                limited_day.append({"_raw": str(w)[:500]})
                        workouts_for_day = limited_day

                    if workouts_for_day:
                        has_found_any = True
                        consecutive_empty = 0
                        days[iso] = workouts_for_day
                    else:
                        if has_found_any:
                            consecutive_empty += 1
                            if should_stop_after_gap(
                                has_found_any_workout=has_found_any,
                                consecutive_empty_days=consecutive_empty,
                                gap_days=dto.gap_days,
                            ):
                                break

                    checked_days += 1
                    cursor = cursor - timedelta(days=1)

                if days:
                    ordered_keys = sort_day_keys_ascending(list(days.keys()))
                    from_date = ordered_keys[0]
                    to_date = ordered_keys[-1]
                    total_workouts = sum(len(days[k]) for k in ordered_keys)
                else:
                    ordered_keys = []
                    from_date = None
                    to_date = None
                    total_workouts = 0

                payload = {
                    "source": "trainingpeaks_selenium_directo",
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                    "athlete_id": athlete_id,
                    "athlete_name": athlete_name,
                    "from_date": from_date,
                    "to_date": to_date,
                    "gap_days": dto.gap_days,
                    "timeout": dto.timeout,
                    "stats": {
                        "days_with_workouts": len(ordered_keys),
                        "total_workouts": total_workouts,
                        "checked_days": checked_days,
                        "error_days": error_days,
                    },
                    "days": {k: days[k] for k in ordered_keys},
                }
            finally:
                try:
                    clear_driver()
                except Exception:
                    pass
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass

            # Persistencia en DB (fuera del lock Selenium).
            await self._update_job(job_id, message="Guardando historial en base de datos...", progress=97)

            async with AsyncSessionLocal() as db:
                repo = AthleteRepository(db)
                athlete = await repo.get_by_id(athlete_id)
                if athlete is None:
                    raise RuntimeError(f"Atleta no encontrado en DB: {athlete_id}")

                current_perf = athlete.performance if isinstance(athlete.performance, dict) else {}
                if current_perf is None:
                    current_perf = {}

                current_perf["training_history"] = payload
                await repo.update(athlete_id, {"performance": current_perf})
                await db.commit()

            await self._update_job(
                job_id,
                status="completed",
                progress=100,
                message="Historial sincronizado y guardado correctamente.",
                completed_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.exception(f"Error en job de historial {job_id}: {e}")
            await self._update_job(
                job_id,
                status="failed",
                progress=100,
                message="Error sincronizando historial.",
                error=str(e),
                completed_at=datetime.now(timezone.utc),
            )


