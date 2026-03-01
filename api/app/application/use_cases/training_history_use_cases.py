"""
Casos de uso para sincronizar el historial de entrenamientos desde TrainingPeaks.

Características clave:
- Flujo separado del chat (endpoint dedicado).
- Usa sesión Selenium dedicada para extracción.
- Serializa acceso al driver por sesión mediante lock.
- Persiste resultado como JSON dentro de `AthleteModel.performance`.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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

        driver = webdriver.Chrome(options=opts)
        wait = WebDriverWait(driver, 10)
        driver.get(TRAININGPEAKS_URL)
        return driver, wait

    async def _run_job(self, *, job_id: str, athlete_id: str, dto: TrainingHistorySyncRequestDTO) -> None:
        """
        Ejecuta la extracción hacia atrás y persiste en DB.

        Criterios de parada (evaluados en orden de prioridad):
        1. Si `dto.from_date` existe, el barrido se detiene al llegar a esa fecha.
        2. Si no, se aplica gap_days: corta tras `gap_days` días vacíos consecutivos
           después de haber encontrado al menos un workout.

        Implementación:
        - Itera día a día hacia atrás desde hoy.
        - Usa funciones de calendario (Selenium) con `use_today` solo en la primera llamada.

        Nota: Las operaciones de Selenium se ejecutan en threads separados via run_selenium()
        para no bloquear el event loop y permitir que el healthcheck responda.
        """
        try:
            await self._update_job(job_id, message="Preparando sesión Selenium...", progress=0, status="running")
            # Obtener nombre del atleta para selección en TrainingPeaks.
            async with AsyncSessionLocal() as db_lookup:
                repo = AthleteRepository(db_lookup)
                athlete = await repo.get_by_id(athlete_id)
                if athlete is None:
                    raise RuntimeError(f"Atleta no encontrado en DB: {athlete_id}")
                # Preferir tp_name (nombre validado de TP) sobre name (de AirTable)
                # para evitar problemas con nombres abreviados o discrepancias.
                athlete_name = athlete.tp_name or athlete.name

            await self._update_job(job_id, message="Creando driver dedicado y autenticando...", progress=1)

            from app.infrastructure.trainingpeaks.tp_domain.core import set_driver, clear_driver
            from app.infrastructure.trainingpeaks.tp_domain.calendar.workout_service import get_all_quickviews_on_date

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

                use_from_date = dto.from_date is not None
                max_days = 365 * 25
                days: Dict[str, Any] = {}

                while checked_days < max_days:
                    # Parada por from_date: no ir mas atras de la fecha solicitada.
                    if use_from_date and cursor < dto.from_date:
                        break

                    iso = cursor.isoformat()

                    if checked_days % 7 == 0:
                        await self._update_job(
                            job_id,
                            message=f"Extrayendo... fecha {iso} (días revisados: {checked_days})",
                            progress=min(95, int((checked_days / max_days) * 100)),
                        )

                    try:
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

                    if workouts_for_day:
                        limited_day: list[dict] = []
                        for w in workouts_for_day:
                            if isinstance(w, dict):
                                limited, _ = enforce_workout_limits(w)
                                limited_day.append(limited)
                            else:
                                limited_day.append({"_raw": str(w)[:500]})
                        workouts_for_day = limited_day

                    if workouts_for_day:
                        has_found_any = True
                        consecutive_empty = 0
                        days[iso] = workouts_for_day
                    else:
                        # Parada por gap solo cuando no se usa from_date.
                        if not use_from_date and has_found_any:
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
                
                # Normalizar datos de TrainingPeaks a formato plano
                await self._update_job(job_id, message="Normalizando datos...", progress=97)
                try:
                    from app.application.services.tp_data_normalizer import TPDataNormalizer
                    
                    normalizer = TPDataNormalizer()
                    normalized_days, validation_summary = normalizer.normalize_history(
                        payload.get("days", {})
                    )
                    
                    logger.info(
                        f"Historial normalizado para {athlete_id}: "
                        f"{validation_summary.total_workouts} workouts, "
                        f"{validation_summary.valid_workouts} validos, "
                        f"calidad: {validation_summary.avg_quality_score:.0%}, "
                        f"status: {validation_summary.workouts_by_status}"
                    )
                    
                    # Guardar datos normalizados junto con raw
                    current_perf["training_history"]["normalized_days"] = normalized_days
                    current_perf["training_history"]["validation_summary"] = {
                        "total_workouts": validation_summary.total_workouts,
                        "valid_workouts": validation_summary.valid_workouts,
                        "avg_quality_score": validation_summary.avg_quality_score,
                        "workouts_by_status": validation_summary.workouts_by_status
                    }
                    
                except Exception as e:
                    logger.warning(f"Error normalizando datos para {athlete_id}: {e}")
                    normalized_days = payload.get("days", {})
                
                # Computar metricas con datos normalizados
                await self._update_job(job_id, message="Computando metricas...", progress=98)
                try:
                    from app.application.services.history_processor import HistoryProcessor
                    
                    processor = HistoryProcessor()
                    metrics = processor.process(normalized_days)
                    current_perf["computed_metrics"] = metrics.to_dict()
                    
                    # Guardar alertas activas
                    current_perf["active_alerts"] = [
                        alert.to_dict() for alert in metrics.active_alerts
                    ]
                    
                    alerts_count = len(metrics.active_alerts)
                    logger.info(
                        f"Metricas computadas para atleta {athlete_id}: "
                        f"CTL={metrics.ctl:.1f}, ATL={metrics.atl:.1f}, "
                        f"TSB={metrics.tsb:.1f}, alertas={alerts_count}"
                    )
                except Exception as e:
                    logger.warning(f"Error computando metricas para {athlete_id}: {e}")
                    # No fallar el job si falla el computo de metricas
                
                await repo.update(athlete_id, {"performance": current_perf})
                await db.commit()

            await self._update_job(
                job_id,
                status="completed",
                progress=100,
                message="Historial sincronizado y metricas computadas correctamente.",
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


