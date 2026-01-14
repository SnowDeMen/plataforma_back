"""
Publicador de planes a TrainingPeaks usando Selenium directo (sin MCP).

Diseño:
- Usa `DriverManager.initialize_training_session(...)` para crear una sesión efímera:
  login con cookies + selección de atleta + Workout Library abierta.
- Reutiliza funciones robustas ya existentes en `plataforma_back/mcp/domain/*`:
  - crear workout en Workout Library
  - drag & drop al calendario

Nota importante:
- Aunque reutilizamos módulos ubicados bajo `mcp/domain`, NO iniciamos MCP ni usamos herramientas MCP.
  Solo aprovechamos utilidades de Selenium ya probadas.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence

from loguru import logger

from app.application.dto.plan_dto import PlanWorkoutDTO
from app.application.interfaces.trainingpeaks_plan_publisher import (
    PlanPublishResult,
    TrainingPeaksPlanPublisher,
)
from app.core.config import settings
from app.infrastructure.driver.driver_manager import DriverManager, DriverSession


@dataclass(frozen=True)
class _NormalizedWorkout:
    """
    Representación normalizada para publicar en TrainingPeaks.
    """

    date_str: str
    workout_type: str
    title: str
    description: Optional[str]
    pre_activity_comments: Optional[str]
    duration: Optional[str]
    distance: Optional[str]
    tss: Optional[int]
    intensity_factor: Optional[float]


def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _is_rest_workout(workout_type: Optional[str]) -> bool:
    t = _normalize_text(workout_type)
    return t in {"day off", "rest"}


def _map_workout_type_to_tp(value: Optional[str]) -> str:
    """
    Mapea tipos que vienen del plan a opciones esperadas por TrainingPeaks.

    TrainingPeaks suele usar etiquetas con capitalización (Run, Bike, Swim, Strength).
    """
    t = _normalize_text(value)
    mapping = {
        "run": "Run",
        "bike": "Bike",
        "swim": "Swim",
        "strength": "Strength",
        "event": "Event",
    }
    if t in mapping:
        return mapping[t]
    return (value or "Run").strip() or "Run"


def _truncate(value: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"


def _compute_date_str(
    *,
    workout: PlanWorkoutDTO,
    plan_start_date: Optional[date],
) -> str:
    """
    Calcula la fecha (YYYY-MM-DD) de forma determinística.

    Prioridad:
    1) `workout.date` si viene en el JSON.
    2) Si hay `plan_start_date`, computar por (week, day) o por day global (1..28).
    """
    if workout.date:
        return str(workout.date)

    if plan_start_date is None:
        raise ValueError("Workout sin 'date' y el plan no tiene 'start_date' para calcularla")

    # Caso A: day dentro de la semana 1..7 y week 1..N.
    if 1 <= workout.week <= 52 and 1 <= workout.day <= 7:
        offset_days = (workout.week - 1) * 7 + (workout.day - 1)
        return str(plan_start_date + timedelta(days=offset_days))

    # Caso B: day global 1..28 (muchos generadores lo usan así).
    if 1 <= workout.day <= 366:
        return str(plan_start_date + timedelta(days=workout.day - 1))

    raise ValueError("No se pudo calcular la fecha del workout (campos week/day inválidos)")


def _normalize_for_publish(
    *,
    plan_id: int,
    index: int,
    workout: PlanWorkoutDTO,
    plan_start_date: Optional[date],
) -> _NormalizedWorkout:
    date_str = _compute_date_str(workout=workout, plan_start_date=plan_start_date)
    base_title = workout.title or workout.workout_type or "Workout"
    # Usar el titulo original tal como se genera en la plataforma
    tp_title = _truncate(base_title.strip(), max_len=90)

    return _NormalizedWorkout(
        date_str=date_str,
        workout_type=_map_workout_type_to_tp(workout.workout_type),
        title=tp_title,
        description=workout.description,
        pre_activity_comments=workout.pre_activity_comments,
        duration=workout.duration,
        distance=workout.distance,
        tss=workout.tss,
        intensity_factor=workout.intensity_factor,
    )


def _find_mcp_domain_path() -> Path:
    """
    Busca el path del módulo que contiene `domain/*` (ubicado dentro de carpeta `mcp/`).

    Lo hacemos de forma robusta para que funcione en desarrollo y Docker,
    sin depender del arranque de MCP.
    """
    current = Path(__file__).resolve()
    for _ in range(8):
        current = current.parent
        mcp_candidate = current / "mcp"
        if mcp_candidate.exists() and (mcp_candidate / "trainingpeaks_mcp_server_modular.py").exists():
            return mcp_candidate
    docker_path = Path("/app/mcp")
    if docker_path.exists():
        return docker_path
    raise FileNotFoundError("No se pudo localizar el módulo 'mcp/' para importar 'domain.*'")


def _ensure_domain_imports_available() -> None:
    """
    Asegura que `domain.*` sea importable agregando `mcp/` al sys.path.
    """
    mcp_path = _find_mcp_domain_path()
    mcp_path_str = str(mcp_path)
    if mcp_path_str not in sys.path:
        sys.path.insert(0, mcp_path_str)


class SeleniumTrainingPeaksPlanPublisher(TrainingPeaksPlanPublisher):
    """
    Implementación real (Selenium) para publicar un plan en TrainingPeaks.
    """

    def publish_plan(
        self,
        *,
        plan_id: int,
        athlete_name: str,
        workouts: Sequence[PlanWorkoutDTO],
        start_date: Optional[date],
        folder_name: Optional[str],
    ) -> PlanPublishResult:
        if not workouts:
            raise ValueError("No se recibieron workouts para aplicar")

        # Validación temprana para evitar abrir/cerrar navegador si no hay nada aplicable.
        publishable_count = sum(1 for w in workouts if not _is_rest_workout(w.workout_type))
        if publishable_count <= 0:
            raise ValueError("Todos los workouts recibidos son de descanso (no hay nada que aplicar)")

        _ensure_domain_imports_available()

        # Imports tardíos: evitamos acoplar el import al arranque del servicio.
        from domain.core import set_driver  # type: ignore
        from domain.workout_library.creation_service import create_workout  # type: ignore
        from domain.calendar.date_service import (  # type: ignore
            drag_workout_to_calendar,
            _ensure_workout_library_folder_open,
        )
        # Imports directos para eliminación (evitamos manage_workout que no pasa folder/exact)
        from domain.workout_library.workout_service import (  # type: ignore
            click_workout,
            click_selected_workout_tomahawk_button,
            click_delete_workout_button,
            click_delete_workout_confirm_button,
        )
        # Import para ocultar workouts fuera de las primeras 2 semanas
        from domain.calendar.workout_service import hide_calendar_workout  # type: ignore

        driver_session: Optional[DriverSession] = None
        skipped_rest = 0
        published = 0
        success = False

        # Regla de negocio requerida por UI: siempre trabajar dentro de la carpeta "Neuronomy"
        # para que el flujo sea determinista (encontrar tiles por título dentro de esa carpeta).
        effective_folder_name = (folder_name or "Neuronomy").strip() or "Neuronomy"

        try:
            logger.info(f"[PlanApply] Creando sesión efímera Selenium para atleta='{athlete_name}'...")
            driver_session = DriverManager.initialize_training_session(athlete_name)

            set_driver(driver_session.driver, driver_session.wait)

            # Publicación determinística en orden estable
            for idx, w in enumerate(workouts, start=1):
                if _is_rest_workout(w.workout_type):
                    skipped_rest += 1
                    continue

                nw = _normalize_for_publish(
                    plan_id=plan_id,
                    index=idx,
                    workout=w,
                    plan_start_date=start_date,
                )

                # Parametros disponibles por tipo de workout
                # Strength: Duration, Calories, TSS, IF (NO tiene Distance)
                # Run/Bike/Swim/etc: Duration, Distance, TSS, IF
                workout_type_lower = nw.workout_type.lower()
                supports_distance = workout_type_lower not in ("strength",)

                planned_values: dict[str, str] = {}
                if nw.duration:
                    planned_values["Duration"] = str(nw.duration)
                if nw.distance and supports_distance:
                    planned_values["Distance"] = str(nw.distance)
                if nw.tss is not None:
                    planned_values["TSS"] = str(nw.tss)
                if nw.intensity_factor is not None:
                    planned_values["IF"] = str(nw.intensity_factor)

                logger.info(f"[PlanApply] Creando workout '{nw.title}' ({nw.workout_type})...")

                # Retry para manejar stale element references despues de muchas operaciones
                max_retries = 2
                result = None

                for attempt in range(max_retries):
                    result = create_workout(
                        folder_name=effective_folder_name,
                        workout_type=nw.workout_type,
                        title=nw.title,
                        description=nw.description,
                        pre_activity_comments=nw.pre_activity_comments,
                        planned_values=planned_values or None,
                        click_save=True,
                    )

                    if "[ERROR]" not in str(result):
                        break  # Exito

                    logger.warning(f"[PlanApply] Intento {attempt + 1} fallo: {result}. Reintentando...")
                    time.sleep(1)

                if "[ERROR]" in str(result):
                    raise RuntimeError(f"TrainingPeaks: fallo creando workout '{nw.title}': {result}")

                # TrainingPeaks abre automaticamente "Recents" al crear un workout.
                # Forzar apertura explicita del folder objetivo para que el drag encuentre el tile correcto.
                logger.info(f"[PlanApply] Abriendo folder '{effective_folder_name}' (colapsando otros)...")
                _ensure_workout_library_folder_open(effective_folder_name, timeout=15)

                logger.info(f"[PlanApply] Arrastrando '{nw.title}' a fecha {nw.date_str}...")
                try:
                    # Intento 1: buscar el tile dentro del folder (ideal cuando el UI está estable).
                    drag_workout_to_calendar(
                        nw.title,
                        nw.date_str,
                        folder=effective_folder_name,
                        exact_title=True,
                        # Ya estamos en calendario; evitar "Go to Today" reduce re-renders y hace el drag más estable.
                        use_today=False,
                    )
                except Exception as e:
                    # Fallback: si no se logra resolver el folder (UI cambiante), intentamos sin folder.
                    logger.warning(
                        f"[PlanApply] Drag con folder='{effective_folder_name}' falló; reintentando sin folder. Error: {e}"
                    )
                    drag_workout_to_calendar(
                        nw.title,
                        nw.date_str,
                        folder=None,
                        exact_title=True,
                        use_today=False,
                    )

                # Ocultar workouts que estan fuera de las primeras 2 semanas del plan.
                # Esto permite mostrar solo las primeras 2 semanas en TrainingPeaks.
                # Dias 1-14 visibles, dia 15+ oculto.
                logger.info(f"[PlanApply] DEBUG hide: start_date={start_date}, workout_date_str={nw.date_str}")
                
                if start_date is not None:
                    # Dia 14 = start_date + 13, dia 15 = start_date + 14
                    # Cutoff = ultimo dia visible (dia 14)
                    cutoff_date = start_date + timedelta(days=13)
                    workout_date = datetime.strptime(nw.date_str, "%Y-%m-%d").date()
                    
                    logger.info(f"[PlanApply] DEBUG hide: cutoff_date={cutoff_date}, workout_date={workout_date}, should_hide={workout_date > cutoff_date}")
                    
                    if workout_date > cutoff_date:
                        logger.info(f"[PlanApply] Ocultando '{nw.title}' (fecha {nw.date_str} > {cutoff_date})...")
                        try:
                            hide_calendar_workout(nw.title, nw.date_str, timeout=12)
                        except Exception as hide_err:
                            # No es critico si falla el hide; el workout ya esta en el calendario.
                            logger.warning(f"[PlanApply] No se pudo ocultar workout: {hide_err}")
                else:
                    logger.warning("[PlanApply] start_date es None, no se puede calcular hide")

                # Eliminar el workout de la Workout Library después del drag exitoso.
                # Esto mantiene la carpeta limpia y evita confusiones con workouts duplicados.
                # Usamos llamadas directas con folder y exact=True para asegurar que eliminamos el correcto.
                logger.info(f"[PlanApply] Eliminando '{nw.title}' de Workout Library...")
                try:
                    # Paso 1: Click en el workout exacto dentro del folder correcto
                    click_workout(nw.title, folder=effective_folder_name, exact=True)
                    # Paso 2: Abrir menú de 3 puntitos (tomahawk)
                    click_selected_workout_tomahawk_button()
                    # Paso 3: Click en opción de eliminar
                    click_delete_workout_button()
                    # Paso 4: Confirmar eliminación
                    click_delete_workout_confirm_button()
                except Exception as del_err:
                    # No es crítico si falla la eliminación; el workout ya está en el calendario.
                    logger.warning(f"[PlanApply] No se pudo eliminar workout de library: {del_err}")

                published += 1

                # Pausa breve para estabilizar UI entre operaciones
                time.sleep(0.5)

            logger.info(
                f"[PlanApply] Publicación completa: published={published}, skipped_rest={skipped_rest}, total={len(workouts)}"
            )

            success = True
            return PlanPublishResult(
                total_workouts=len(workouts),
                skipped_rest_workouts=skipped_rest,
                published_workouts=published,
            )

        except Exception as e:
            # Si falla muy pronto (p.ej. no encuentra carpeta), en modo GUI conviene
            # dejar el navegador abierto para inspección manual.
            logger.exception(f"[PlanApply] Error publicando plan (plan_id={plan_id}): {e}")
            raise

        finally:
            # Desconectar el módulo `domain.core` del driver, aunque el driver lo cierre DriverManager.
            try:
                _ensure_domain_imports_available()
                from domain.core import clear_driver  # type: ignore
                clear_driver()
            except Exception:
                pass

            # Cierre del driver:
            # - En éxito: siempre cerrar para liberar recursos.
            # - En error: cerrar solo en headless (producción). En GUI (desarrollo) lo dejamos abierto.
            should_close = driver_session is not None and (success or settings.SELENIUM_HEADLESS)
            if should_close and driver_session is not None:
                try:
                    DriverManager.close_session(driver_session.session_id)
                except Exception as e:
                    logger.warning(f"[PlanApply] Error cerrando sesión Selenium efímera: {e}")


