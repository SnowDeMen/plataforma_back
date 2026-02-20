"""
Tests unitarios para HistoryProcessor.

Verifica el calculo correcto de metricas de entrenamiento:
- CTL/ATL/TSB (modelo Banister)
- Adherencia y consistencia
- Distribucion de intensidad
- Patrones y tendencias
"""
import pytest
from datetime import date, datetime, timedelta

from app.application.services.history_processor import HistoryProcessor
from app.domain.entities.training_metrics import ComputedMetrics


class TestHistoryProcessor:
    """Tests para HistoryProcessor."""
    
    @pytest.fixture
    def processor(self):
        """Crea una instancia del procesador."""
        return HistoryProcessor()
    
    @pytest.fixture
    def sample_history(self):
        """Genera un historial de ejemplo con 30 dias de datos."""
        today = date.today()
        days = {}
        
        for i in range(30):
            workout_date = today - timedelta(days=i)
            date_str = workout_date.isoformat()
            
            # Crear workout cada 2 dias (simulando ~15 workouts)
            if i % 2 == 0:
                days[date_str] = [{
                    "title": f"Workout {i}",
                    "workout_type": "Run" if i % 4 == 0 else "Bike",
                    "status": "completed",
                    "duration_completed": "1:00:00",
                    "distance_completed": 10 if i % 4 == 0 else 25,
                    "tss_completed": 50 + (i * 2),
                    "if": 0.70 + (i * 0.01),
                }]
        
        return days
    
    @pytest.fixture
    def empty_history(self):
        """Historial vacio."""
        return {}
    
    @pytest.fixture
    def history_with_skipped(self):
        """Historial con workouts omitidos."""
        today = date.today()
        days = {}
        
        for i in range(10):
            workout_date = today - timedelta(days=i)
            date_str = workout_date.isoformat()
            
            # 50% completados, 50% omitidos
            status = "completed" if i % 2 == 0 else "skipped"
            
            days[date_str] = [{
                "title": f"Workout {i}",
                "workout_type": "Run",
                "status": status,
                "duration_completed": "0:45:00" if status == "completed" else None,
                "tss_completed": 40 if status == "completed" else None,
                "if": 0.75,
            }]
        
        return days
    
    def test_process_empty_history(self, processor, empty_history):
        """Procesar historial vacio debe retornar metricas en cero."""
        metrics = processor.process(empty_history, period_days=30)
        
        assert isinstance(metrics, ComputedMetrics)
        assert metrics.total_workouts == 0
        assert metrics.ctl == 0.0
        assert metrics.atl == 0.0
        assert metrics.tsb == 0.0
        assert metrics.adherence_rate == 0.0
    
    def test_process_sample_history(self, processor, sample_history):
        """Procesar historial de ejemplo debe calcular metricas correctamente."""
        metrics = processor.process(sample_history, period_days=30)
        
        assert isinstance(metrics, ComputedMetrics)
        assert metrics.total_workouts > 0
        assert metrics.total_completed > 0
        assert metrics.total_hours > 0
        assert metrics.total_tss > 0
        
        # CTL debe ser positivo si hay entrenamientos
        assert metrics.ctl >= 0
        assert metrics.atl >= 0
        
        # TSB = CTL - ATL
        assert abs(metrics.tsb - (metrics.ctl - metrics.atl)) < 0.1
    
    def test_adherence_calculation(self, processor, history_with_skipped):
        """Adherencia debe reflejar workouts completados vs totales."""
        metrics = processor.process(history_with_skipped, period_days=30)
        
        # Con 50% completados y 50% omitidos, adherencia debe ser ~0.5
        assert 0.4 <= metrics.adherence_rate <= 0.6
    
    def test_intensity_distribution(self, processor, sample_history):
        """Distribucion de intensidad debe sumar ~100%."""
        metrics = processor.process(sample_history, period_days=30)
        
        total_distribution = (
            metrics.pct_easy + 
            metrics.pct_moderate + 
            metrics.pct_hard
        )
        
        # Debe sumar aproximadamente 1.0 (100%)
        assert 0.99 <= total_distribution <= 1.01
    
    def test_period_filtering(self, processor):
        """El procesador debe filtrar correctamente por periodo."""
        today = date.today()
        
        # Crear historial con datos dentro y fuera del periodo
        days = {}
        
        # Dentro del periodo (hace 10 dias)
        recent_date = (today - timedelta(days=10)).isoformat()
        days[recent_date] = [{
            "title": "Recent workout",
            "status": "completed",
            "tss_completed": 50,
        }]
        
        # Fuera del periodo (hace 100 dias)
        old_date = (today - timedelta(days=100)).isoformat()
        days[old_date] = [{
            "title": "Old workout",
            "status": "completed",
            "tss_completed": 100,
        }]
        
        # Procesar con periodo de 30 dias
        metrics = processor.process(days, period_days=30)
        
        # Solo debe contar el workout reciente
        assert metrics.total_completed == 1
        assert metrics.total_tss == 50
    
    def test_to_dict_serialization(self, processor, sample_history):
        """Las metricas deben ser serializables a dict."""
        metrics = processor.process(sample_history, period_days=30)
        metrics_dict = metrics.to_dict()
        
        assert isinstance(metrics_dict, dict)
        assert "computed_at" in metrics_dict
        assert "ctl" in metrics_dict
        assert "atl" in metrics_dict
        assert "tsb" in metrics_dict
        assert "adherence_rate" in metrics_dict
        
        # Verificar que datetime se serializa como string
        assert isinstance(metrics_dict["computed_at"], str)
    
    def test_from_dict_deserialization(self, processor, sample_history):
        """Las metricas deben ser deserializables desde dict."""
        original = processor.process(sample_history, period_days=30)
        metrics_dict = original.to_dict()
        
        # Deserializar
        restored = ComputedMetrics.from_dict(metrics_dict)
        
        assert isinstance(restored, ComputedMetrics)
        assert restored.ctl == original.ctl
        assert restored.atl == original.atl
        assert restored.tsb == original.tsb
        assert restored.total_workouts == original.total_workouts


class TestCTLATLCalculation:
    """Tests especificos para calculos de CTL/ATL/TSB."""
    
    @pytest.fixture
    def processor(self):
        return HistoryProcessor()
    
    def test_high_recent_load_increases_atl(self, processor):
        """Carga reciente alta debe aumentar ATL mas que CTL."""
        today = date.today()
        days = {}
        
        # Ultimos 7 dias con carga muy alta
        for i in range(7):
            date_str = (today - timedelta(days=i)).isoformat()
            days[date_str] = [{
                "status": "completed",
                "tss_completed": 150,  # TSS alto
            }]
        
        metrics = processor.process(days, period_days=30)
        
        # Con solo 7 dias de datos recientes, ATL debe ser alto
        # y TSB probablemente negativo
        assert metrics.atl > 0
        assert metrics.tsb < 0 or metrics.atl >= metrics.ctl
    
    def test_no_recent_training_positive_tsb(self, processor):
        """Sin entrenamiento reciente, TSB debe tender a 0."""
        today = date.today()
        days = {}
        
        # Solo datos de hace 20-30 dias, nada reciente
        for i in range(20, 30):
            date_str = (today - timedelta(days=i)).isoformat()
            days[date_str] = [{
                "status": "completed",
                "tss_completed": 50,
            }]
        
        metrics = processor.process(days, period_days=30)
        
        # ATL debe ser bajo porque no hay carga reciente
        # CTL tiene algo por los entrenamientos antiguos
        assert metrics.atl < metrics.ctl or metrics.atl < 20


class TestPatternDetection:
    """Tests para deteccion de patrones."""
    
    @pytest.fixture
    def processor(self):
        return HistoryProcessor()
    
    def test_preferred_days_detection(self, processor):
        """Debe detectar dias preferidos de entrenamiento."""
        today = date.today()
        days = {}
        
        # Crear workouts siempre en lunes (weekday 0)
        for week in range(8):
            # Encontrar el proximo lunes
            days_until_monday = (7 - today.weekday()) % 7 or 7
            monday = today - timedelta(days=week*7) + timedelta(days=-today.weekday())
            
            if monday <= today:
                date_str = monday.isoformat()
                days[date_str] = [{
                    "status": "completed",
                    "tss_completed": 50,
                }]
        
        metrics = processor.process(days, period_days=60)
        
        # Debe detectar Mon como dia preferido
        if metrics.preferred_workout_days:
            assert "Mon" in metrics.preferred_workout_days
    
    def test_streak_calculation(self, processor):
        """Debe calcular rachas correctamente."""
        today = date.today()
        days = {}
        
        # Crear una racha de 5 dias consecutivos
        for i in range(5):
            date_str = (today - timedelta(days=i)).isoformat()
            days[date_str] = [{
                "status": "completed",
                "tss_completed": 40,
            }]
        
        metrics = processor.process(days, period_days=30)
        
        assert metrics.longest_streak == 5
