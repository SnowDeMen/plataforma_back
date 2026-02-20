"""
Sistema de alertas extensible para entrenamiento.

Define el protocolo AlertRule que permite agregar nuevas alertas
sin modificar codigo existente (Open/Closed Principle).

Uso futuro:
- Alertas basadas en HRV (integracion wearables)
- Alertas de sueno (integracion wearables)
- Alertas de nutricion
- Alertas de competencia proxima
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Protocol, List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.entities.training_metrics import ComputedMetrics


class AlertSeverity(Enum):
    """
    Severidad de la alerta.
    
    Define el nivel de urgencia de la alerta para el atleta/coach.
    """
    INFO = "info"           # Informativo, no requiere accion inmediata
    WARNING = "warning"     # Requiere atencion, posible riesgo
    CRITICAL = "critical"   # Accion inmediata requerida, riesgo alto


class AlertCategory(Enum):
    """
    Categorias de alertas.
    
    Permite filtrar y agrupar alertas por tipo.
    Extensible para futuras integraciones.
    """
    LOAD = "load"               # Carga de entrenamiento (CTL, ATL, ramp rate)
    RECOVERY = "recovery"       # Recuperacion (TSB, fatiga)
    ADHERENCE = "adherence"     # Adherencia al plan (% completado)
    PERFORMANCE = "performance" # Rendimiento (polarizacion, tendencias)
    HEALTH = "health"           # Salud (futuro: HRV, sueno, etc)


@dataclass
class TrainingAlert:
    """
    Alerta generada por el sistema de evaluacion.
    
    Representa una condicion que requiere atencion del atleta o coach.
    Incluye contexto suficiente para entender y actuar sobre la alerta.
    """
    
    id: str                     # Identificador unico (ej: "high_ramp_rate")
    category: AlertCategory     # Categoria de la alerta
    severity: AlertSeverity     # Severidad (info, warning, critical)
    title: str                  # Titulo corto para UI
    message: str                # Mensaje descriptivo con contexto
    recommendation: str         # Que hacer al respecto
    value: float               # Valor actual que disparo la alerta
    threshold: float           # Umbral configurado para la alerta
    created_at: datetime       # Cuando se genero la alerta
    
    # Metadata extensible para integraciones futuras
    # Permite agregar datos adicionales sin cambiar la estructura
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la alerta a diccionario para persistencia/API."""
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "recommendation": self.recommendation,
            "value": self.value,
            "threshold": self.threshold,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingAlert":
        """Crea una instancia desde diccionario."""
        return cls(
            id=data["id"],
            category=AlertCategory(data["category"]),
            severity=AlertSeverity(data["severity"]),
            title=data["title"],
            message=data["message"],
            recommendation=data["recommendation"],
            value=data["value"],
            threshold=data["threshold"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {})
        )


class AlertRule(Protocol):
    """
    Protocolo para reglas de alerta.
    
    Cualquier clase que implemente este protocolo puede ser registrada
    en AlertRegistry para evaluacion automatica.
    
    Ejemplo de implementacion:
    
    ```python
    @dataclass
    class MyCustomAlert:
        id: str = "my_alert"
        category: AlertCategory = AlertCategory.HEALTH
        
        def evaluate(self, metrics, context) -> Optional[TrainingAlert]:
            if some_condition:
                return TrainingAlert(...)
            return None
    ```
    """
    
    id: str
    category: AlertCategory
    
    def evaluate(
        self, 
        metrics: "ComputedMetrics", 
        context: Dict[str, Any]
    ) -> Optional[TrainingAlert]:
        """
        Evalua la regla contra las metricas actuales.
        
        Args:
            metrics: Metricas computadas del atleta
            context: Contexto adicional (datos de wearables, calendario, etc)
            
        Returns:
            TrainingAlert si la condicion se cumple, None si no
        """
        ...


class AlertRegistry:
    """
    Registro central de reglas de alerta.
    
    Singleton que permite:
    - Registrar nuevas reglas dinamicamente
    - Evaluar todas las reglas en un solo paso
    - Filtrar reglas por categoria
    
    Las reglas se registran en el startup de la aplicacion
    (ver app/core/events.py).
    """
    
    _rules: List[AlertRule] = []
    _initialized: bool = False
    
    @classmethod
    def register(cls, rule: AlertRule) -> None:
        """
        Registra una nueva regla de alerta.
        
        Args:
            rule: Instancia que implementa AlertRule protocol
        """
        # Evitar duplicados por id
        existing_ids = {r.id for r in cls._rules}
        if rule.id not in existing_ids:
            cls._rules.append(rule)
    
    @classmethod
    def unregister(cls, rule_id: str) -> bool:
        """
        Elimina una regla del registro.
        
        Args:
            rule_id: ID de la regla a eliminar
            
        Returns:
            True si se elimino, False si no existia
        """
        initial_count = len(cls._rules)
        cls._rules = [r for r in cls._rules if r.id != rule_id]
        return len(cls._rules) < initial_count
    
    @classmethod
    def evaluate_all(
        cls, 
        metrics: "ComputedMetrics", 
        context: Optional[Dict[str, Any]] = None
    ) -> List[TrainingAlert]:
        """
        Evalua todas las reglas registradas.
        
        Args:
            metrics: Metricas computadas del atleta
            context: Contexto adicional opcional
            
        Returns:
            Lista de alertas activas (reglas que dispararon)
        """
        alerts = []
        ctx = context or {}
        
        for rule in cls._rules:
            try:
                alert = rule.evaluate(metrics, ctx)
                if alert is not None:
                    alerts.append(alert)
            except Exception as e:
                # Log error pero continua con otras reglas
                # No queremos que una regla rota detenga todo
                import logging
                logging.warning(f"Error evaluando regla {rule.id}: {e}")
        
        return alerts
    
    @classmethod
    def get_rules_by_category(cls, category: AlertCategory) -> List[AlertRule]:
        """
        Obtiene reglas filtradas por categoria.
        
        Args:
            category: Categoria a filtrar
            
        Returns:
            Lista de reglas de esa categoria
        """
        return [r for r in cls._rules if r.category == category]
    
    @classmethod
    def get_all_rules(cls) -> List[AlertRule]:
        """Retorna todas las reglas registradas."""
        return cls._rules.copy()
    
    @classmethod
    def clear(cls) -> None:
        """
        Limpia todas las reglas registradas.
        Util para testing.
        """
        cls._rules = []
        cls._initialized = False
    
    @classmethod
    def is_initialized(cls) -> bool:
        """Verifica si el registro ya fue inicializado."""
        return cls._initialized
    
    @classmethod
    def mark_initialized(cls) -> None:
        """Marca el registro como inicializado."""
        cls._initialized = True
