"""
Evaluadores de alertas base del sistema.

Implementa las reglas de alerta iniciales basadas en metricas computadas.
Para agregar nuevas alertas, crear clases que implementen AlertRule
y registrarlas via AlertRegistry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional

from app.domain.entities.alerts import (
    AlertCategory,
    AlertSeverity,
    TrainingAlert,
    AlertRegistry
)
from app.domain.entities.training_metrics import ComputedMetrics


@dataclass
class HighRampRateAlert:
    """
    Alerta cuando el ramp rate es muy alto.
    
    Un ramp rate > 5 TSS/dia/semana indica incremento rapido de carga
    que puede llevar a sobreentrenamiento o lesion.
    """
    
    id: str = "high_ramp_rate"
    category: AlertCategory = AlertCategory.LOAD
    threshold: float = 5.0  # TSS/dia/semana
    critical_threshold: float = 8.0
    
    def evaluate(
        self, 
        metrics: ComputedMetrics, 
        context: Dict[str, Any]
    ) -> Optional[TrainingAlert]:
        """Evalua si el ramp rate excede el umbral."""
        if metrics.ramp_rate > self.threshold:
            severity = (
                AlertSeverity.CRITICAL 
                if metrics.ramp_rate >= self.critical_threshold 
                else AlertSeverity.WARNING
            )
            
            return TrainingAlert(
                id=self.id,
                category=self.category,
                severity=severity,
                title="Incremento rapido de carga",
                message=(
                    f"Tu ramp rate es {metrics.ramp_rate:.1f} TSS/dia/semana "
                    f"(umbral: {self.threshold})"
                ),
                recommendation=(
                    "Considera reducir el volumen esta semana para "
                    "evitar sobreentrenamiento o lesion"
                ),
                value=metrics.ramp_rate,
                threshold=self.threshold,
                created_at=datetime.utcnow(),
                metadata={"ctl": metrics.ctl, "atl": metrics.atl}
            )
        return None


@dataclass
class LowAdherenceAlert:
    """
    Alerta cuando la adherencia al plan es baja.
    
    Una adherencia < 70% indica que el atleta no esta siguiendo
    el plan, ya sea por falta de tiempo o un plan demasiado exigente.
    """
    
    id: str = "low_adherence"
    category: AlertCategory = AlertCategory.ADHERENCE
    threshold: float = 0.70  # 70%
    warning_threshold: float = 0.50  # 50%
    
    def evaluate(
        self, 
        metrics: ComputedMetrics, 
        context: Dict[str, Any]
    ) -> Optional[TrainingAlert]:
        """Evalua si la adherencia esta por debajo del umbral."""
        if metrics.adherence_rate < self.threshold:
            severity = (
                AlertSeverity.WARNING 
                if metrics.adherence_rate < self.warning_threshold 
                else AlertSeverity.INFO
            )
            
            return TrainingAlert(
                id=self.id,
                category=self.category,
                severity=severity,
                title="Adherencia por debajo del objetivo",
                message=(
                    f"Has completado {metrics.adherence_rate:.0%} de tus "
                    f"entrenamientos (objetivo: {self.threshold:.0%})"
                ),
                recommendation=(
                    "Revisa si el plan es realista para tu disponibilidad actual. "
                    "Considera ajustar el numero de sesiones semanales."
                ),
                value=metrics.adherence_rate,
                threshold=self.threshold,
                created_at=datetime.utcnow(),
                metadata={
                    "total_workouts": metrics.total_workouts,
                    "completed": metrics.total_completed
                }
            )
        return None


@dataclass
class NegativeTSBAlert:
    """
    Alerta cuando el TSB es muy negativo.
    
    Un TSB muy negativo indica fatiga acumulada significativa.
    TSB = CTL - ATL, donde valores < -20 sugieren riesgo.
    """
    
    id: str = "negative_tsb"
    category: AlertCategory = AlertCategory.RECOVERY
    threshold: float = -20.0
    critical_threshold: float = -30.0
    
    def evaluate(
        self, 
        metrics: ComputedMetrics, 
        context: Dict[str, Any]
    ) -> Optional[TrainingAlert]:
        """Evalua si el TSB indica fatiga excesiva."""
        if metrics.tsb < self.threshold:
            severity = (
                AlertSeverity.CRITICAL 
                if metrics.tsb < self.critical_threshold 
                else AlertSeverity.WARNING
            )
            
            return TrainingAlert(
                id=self.id,
                category=self.category,
                severity=severity,
                title="Fatiga acumulada alta",
                message=(
                    f"Tu TSB es {metrics.tsb:.0f} (forma negativa indica fatiga). "
                    f"Umbral de alerta: {self.threshold:.0f}"
                ),
                recommendation=(
                    "Incluye dias de recuperacion activa o descanso completo. "
                    "Considera reducir intensidad los proximos dias."
                ),
                value=metrics.tsb,
                threshold=self.threshold,
                created_at=datetime.utcnow(),
                metadata={
                    "ctl": metrics.ctl, 
                    "atl": metrics.atl,
                    "load_status": metrics.get_load_status()
                }
            )
        return None


@dataclass
class PolarizationAlert:
    """
    Alerta cuando la distribucion de intensidad no es polarizada.
    
    La regla 80/20 sugiere que ~80% del entrenamiento debe ser
    en zonas faciles (Z1-Z2) para optimizar adaptaciones.
    """
    
    id: str = "low_polarization"
    category: AlertCategory = AlertCategory.PERFORMANCE
    threshold: float = 0.70  # Al menos 70% en Z1-Z2
    
    def evaluate(
        self, 
        metrics: ComputedMetrics, 
        context: Dict[str, Any]
    ) -> Optional[TrainingAlert]:
        """Evalua si la distribucion de intensidad es adecuada."""
        # Solo alertar si hay suficientes datos
        if metrics.total_completed < 5:
            return None
        
        if metrics.pct_easy < self.threshold:
            return TrainingAlert(
                id=self.id,
                category=self.category,
                severity=AlertSeverity.INFO,
                title="Distribucion de intensidad no optima",
                message=(
                    f"Solo {metrics.pct_easy:.0%} de tu entrenamiento es en zona facil "
                    f"(recomendado: {self.threshold:.0%}+)"
                ),
                recommendation=(
                    "Agrega mas rodajes suaves para mejorar base aerobica. "
                    "Evita entrenar en 'zona gris' (Z3) con frecuencia."
                ),
                value=metrics.pct_easy,
                threshold=self.threshold,
                created_at=datetime.utcnow(),
                metadata={
                    "pct_easy": metrics.pct_easy,
                    "pct_moderate": metrics.pct_moderate,
                    "pct_hard": metrics.pct_hard,
                    "polarization_status": metrics.get_polarization_status()
                }
            )
        return None


@dataclass
class LongGapAlert:
    """
    Alerta cuando hay un gap muy largo sin entrenar.
    
    Gaps > 7 dias pueden indicar problemas de motivacion,
    lesion, o simplemente olvido.
    """
    
    id: str = "long_gap"
    category: AlertCategory = AlertCategory.ADHERENCE
    threshold: int = 7  # dias
    
    def evaluate(
        self, 
        metrics: ComputedMetrics, 
        context: Dict[str, Any]
    ) -> Optional[TrainingAlert]:
        """Evalua si hay gaps largos sin entrenar."""
        if metrics.longest_gap > self.threshold:
            return TrainingAlert(
                id=self.id,
                category=self.category,
                severity=AlertSeverity.INFO,
                title="Gap largo detectado",
                message=(
                    f"Hubo un periodo de {metrics.longest_gap} dias sin "
                    f"entrenamientos completados"
                ),
                recommendation=(
                    "Revisa si hubo alguna razon especifica (viaje, enfermedad). "
                    "Considera ajustar el plan para evitar gaps futuros."
                ),
                value=float(metrics.longest_gap),
                threshold=float(self.threshold),
                created_at=datetime.utcnow()
            )
        return None


def register_default_alerts() -> None:
    """
    Registra las alertas base del sistema.
    
    Debe llamarse una vez al iniciar la aplicacion (en events.py startup).
    """
    if AlertRegistry.is_initialized():
        return
    
    AlertRegistry.register(HighRampRateAlert())
    AlertRegistry.register(LowAdherenceAlert())
    AlertRegistry.register(NegativeTSBAlert())
    AlertRegistry.register(PolarizationAlert())
    AlertRegistry.register(LongGapAlert())
    
    AlertRegistry.mark_initialized()


def get_default_evaluators() -> list:
    """
    Retorna instancias de los evaluadores por defecto.
    Util para testing.
    """
    return [
        HighRampRateAlert(),
        LowAdherenceAlert(),
        NegativeTSBAlert(),
        PolarizationAlert(),
        LongGapAlert(),
    ]
