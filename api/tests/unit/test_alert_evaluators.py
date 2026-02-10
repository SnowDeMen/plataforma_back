"""
Tests unitarios para evaluadores de alertas.

Verifica que cada evaluador genera alertas correctamente
basado en los umbrales configurados.
"""
import pytest
from datetime import date, datetime

from app.domain.entities.training_metrics import ComputedMetrics
from app.domain.entities.alerts import (
    AlertRegistry,
    AlertCategory,
    AlertSeverity,
    TrainingAlert
)
from app.application.services.alert_evaluators import (
    HighRampRateAlert,
    LowAdherenceAlert,
    NegativeTSBAlert,
    PolarizationAlert,
    LongGapAlert,
    register_default_alerts,
    get_default_evaluators
)


@pytest.fixture
def base_metrics():
    """
    Metricas base sin ninguna condicion de alerta.
    Valores saludables/neutrales.
    """
    return ComputedMetrics(
        computed_at=datetime.utcnow(),
        period_days=90,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 3, 31),
        total_workouts=30,
        total_completed=28,
        total_skipped=2,
        total_hours=40.0,
        total_distance_km=400.0,
        total_tss=2000,
        total_elevation_m=5000,
        avg_weekly_hours=3.5,
        avg_weekly_distance=30.0,
        avg_weekly_tss=150.0,
        avg_workouts_per_week=3.0,
        avg_workout_duration_min=60.0,
        ctl=45.0,
        atl=40.0,
        tsb=5.0,  # TSB positivo, bien descansado
        ramp_rate=2.0,  # Ramp rate bajo
        adherence_rate=0.85,  # Buena adherencia
        consistency_score=0.80,
        pct_easy=0.75,  # Buena polarizacion
        pct_moderate=0.15,
        pct_hard=0.10,
        longest_gap=3,  # Gap corto
    )


class TestHighRampRateAlert:
    """Tests para HighRampRateAlert."""
    
    @pytest.fixture
    def evaluator(self):
        return HighRampRateAlert()
    
    def test_no_alert_below_threshold(self, evaluator, base_metrics):
        """No debe generar alerta si ramp rate < umbral."""
        base_metrics.ramp_rate = 3.0
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is None
    
    def test_warning_alert_above_threshold(self, evaluator, base_metrics):
        """Debe generar alerta WARNING si ramp rate > umbral."""
        base_metrics.ramp_rate = 6.0
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.id == "high_ramp_rate"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.category == AlertCategory.LOAD
    
    def test_critical_alert_very_high(self, evaluator, base_metrics):
        """Debe generar alerta CRITICAL si ramp rate muy alto."""
        base_metrics.ramp_rate = 9.0
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL


class TestLowAdherenceAlert:
    """Tests para LowAdherenceAlert."""
    
    @pytest.fixture
    def evaluator(self):
        return LowAdherenceAlert()
    
    def test_no_alert_good_adherence(self, evaluator, base_metrics):
        """No debe generar alerta si adherencia > umbral."""
        base_metrics.adherence_rate = 0.85
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is None
    
    def test_info_alert_low_adherence(self, evaluator, base_metrics):
        """Debe generar alerta INFO si adherencia moderadamente baja."""
        base_metrics.adherence_rate = 0.60
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.id == "low_adherence"
        assert alert.severity == AlertSeverity.INFO
    
    def test_warning_alert_very_low_adherence(self, evaluator, base_metrics):
        """Debe generar alerta WARNING si adherencia muy baja."""
        base_metrics.adherence_rate = 0.40
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING


class TestNegativeTSBAlert:
    """Tests para NegativeTSBAlert."""
    
    @pytest.fixture
    def evaluator(self):
        return NegativeTSBAlert()
    
    def test_no_alert_positive_tsb(self, evaluator, base_metrics):
        """No debe generar alerta si TSB > umbral."""
        base_metrics.tsb = 5.0
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is None
    
    def test_no_alert_moderate_negative_tsb(self, evaluator, base_metrics):
        """No debe generar alerta si TSB moderadamente negativo."""
        base_metrics.tsb = -10.0
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is None
    
    def test_warning_alert_very_negative_tsb(self, evaluator, base_metrics):
        """Debe generar alerta WARNING si TSB muy negativo."""
        base_metrics.tsb = -25.0
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.id == "negative_tsb"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.category == AlertCategory.RECOVERY
    
    def test_critical_alert_extreme_negative_tsb(self, evaluator, base_metrics):
        """Debe generar alerta CRITICAL si TSB extremadamente negativo."""
        base_metrics.tsb = -35.0
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL


class TestPolarizationAlert:
    """Tests para PolarizationAlert."""
    
    @pytest.fixture
    def evaluator(self):
        return PolarizationAlert()
    
    def test_no_alert_good_polarization(self, evaluator, base_metrics):
        """No debe generar alerta si distribucion bien polarizada."""
        base_metrics.pct_easy = 0.80
        base_metrics.total_completed = 10
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is None
    
    def test_info_alert_poor_polarization(self, evaluator, base_metrics):
        """Debe generar alerta INFO si distribucion no polarizada."""
        base_metrics.pct_easy = 0.55
        base_metrics.pct_moderate = 0.30
        base_metrics.pct_hard = 0.15
        base_metrics.total_completed = 10
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.id == "low_polarization"
        assert alert.severity == AlertSeverity.INFO
    
    def test_no_alert_insufficient_data(self, evaluator, base_metrics):
        """No debe generar alerta si hay pocos datos."""
        base_metrics.pct_easy = 0.50
        base_metrics.total_completed = 3  # Menos de 5
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is None


class TestLongGapAlert:
    """Tests para LongGapAlert."""
    
    @pytest.fixture
    def evaluator(self):
        return LongGapAlert()
    
    def test_no_alert_short_gap(self, evaluator, base_metrics):
        """No debe generar alerta si gaps son cortos."""
        base_metrics.longest_gap = 3
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is None
    
    def test_info_alert_long_gap(self, evaluator, base_metrics):
        """Debe generar alerta INFO si hay gap largo."""
        base_metrics.longest_gap = 10
        
        alert = evaluator.evaluate(base_metrics, {})
        
        assert alert is not None
        assert alert.id == "long_gap"
        assert alert.severity == AlertSeverity.INFO


class TestAlertRegistry:
    """Tests para AlertRegistry."""
    
    @pytest.fixture(autouse=True)
    def clean_registry(self):
        """Limpia el registro antes de cada test."""
        AlertRegistry.clear()
        yield
        AlertRegistry.clear()
    
    def test_register_and_evaluate(self, base_metrics):
        """Debe registrar y evaluar alertas correctamente."""
        AlertRegistry.register(HighRampRateAlert())
        
        # Configurar para disparar alerta
        base_metrics.ramp_rate = 7.0
        
        alerts = AlertRegistry.evaluate_all(base_metrics)
        
        assert len(alerts) == 1
        assert alerts[0].id == "high_ramp_rate"
    
    def test_no_duplicate_registration(self, base_metrics):
        """No debe registrar alertas duplicadas."""
        AlertRegistry.register(HighRampRateAlert())
        AlertRegistry.register(HighRampRateAlert())
        
        rules = AlertRegistry.get_all_rules()
        
        assert len(rules) == 1
    
    def test_filter_by_category(self):
        """Debe filtrar reglas por categoria."""
        AlertRegistry.register(HighRampRateAlert())  # LOAD
        AlertRegistry.register(NegativeTSBAlert())   # RECOVERY
        AlertRegistry.register(LowAdherenceAlert())  # ADHERENCE
        
        load_rules = AlertRegistry.get_rules_by_category(AlertCategory.LOAD)
        
        assert len(load_rules) == 1
        assert load_rules[0].category == AlertCategory.LOAD
    
    def test_register_default_alerts(self):
        """Debe registrar todas las alertas por defecto."""
        register_default_alerts()
        
        rules = AlertRegistry.get_all_rules()
        
        # Deben estar todas las alertas base
        assert len(rules) >= 5
        
        rule_ids = {r.id for r in rules}
        assert "high_ramp_rate" in rule_ids
        assert "low_adherence" in rule_ids
        assert "negative_tsb" in rule_ids
        assert "low_polarization" in rule_ids
        assert "long_gap" in rule_ids
    
    def test_evaluate_multiple_alerts(self, base_metrics):
        """Debe evaluar multiples alertas y retornar las activas."""
        register_default_alerts()
        
        # Configurar metricas para disparar multiples alertas
        base_metrics.ramp_rate = 7.0     # Dispara high_ramp_rate
        base_metrics.adherence_rate = 0.50  # Dispara low_adherence
        base_metrics.tsb = -25.0          # Dispara negative_tsb
        
        alerts = AlertRegistry.evaluate_all(base_metrics)
        
        assert len(alerts) >= 3
        
        alert_ids = {a.id for a in alerts}
        assert "high_ramp_rate" in alert_ids
        assert "low_adherence" in alert_ids
        assert "negative_tsb" in alert_ids


class TestAlertSerialization:
    """Tests para serializacion de alertas."""
    
    def test_alert_to_dict(self):
        """Debe serializar alerta a diccionario."""
        alert = TrainingAlert(
            id="test_alert",
            category=AlertCategory.LOAD,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="Test message",
            recommendation="Test recommendation",
            value=7.5,
            threshold=5.0,
            created_at=datetime(2025, 2, 1, 12, 0, 0),
            metadata={"extra": "data"}
        )
        
        alert_dict = alert.to_dict()
        
        assert alert_dict["id"] == "test_alert"
        assert alert_dict["category"] == "load"
        assert alert_dict["severity"] == "warning"
        assert alert_dict["value"] == 7.5
        assert "extra" in alert_dict["metadata"]
    
    def test_alert_from_dict(self):
        """Debe deserializar alerta desde diccionario."""
        alert_dict = {
            "id": "test_alert",
            "category": "load",
            "severity": "warning",
            "title": "Test Alert",
            "message": "Test message",
            "recommendation": "Test recommendation",
            "value": 7.5,
            "threshold": 5.0,
            "created_at": "2025-02-01T12:00:00",
            "metadata": {"extra": "data"}
        }
        
        alert = TrainingAlert.from_dict(alert_dict)
        
        assert alert.id == "test_alert"
        assert alert.category == AlertCategory.LOAD
        assert alert.severity == AlertSeverity.WARNING
        assert alert.value == 7.5
