"""
Interfaz para publicar (aplicar) un plan de entrenamiento en TrainingPeaks.

Este contrato existe para:
- Mantener Clean Architecture: los casos de uso no dependen de Selenium directamente.
- Facilitar tests unitarios sin levantar navegador.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Protocol, Sequence

from app.application.dto.plan_dto import PlanWorkoutDTO


@dataclass(frozen=True)
class PlanPublishResult:
    """
    Resultado resumido de una publicación.

    Se mantiene pequeño y determinista para logging y UI.
    """

    total_workouts: int
    skipped_rest_workouts: int
    published_workouts: int


class TrainingPeaksPlanPublisher(Protocol):
    """
    Publica workouts de un plan hacia TrainingPeaks.

    Implementaciones:
    - Selenium directo.
    - Fake/stub para tests.
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
        """
        Publica un plan hacia TrainingPeaks.

        Reglas del caso de uso:
        - Si hay cualquier error, debe lanzar excepción para que el caso de uso
          NO marque el plan como aplicado.
        """


