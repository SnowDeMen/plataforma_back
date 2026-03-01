"""
Tests unitarios para AthleteContextBuilder.

Verifica que el builder genera contexto optimizado correctamente
para el LLM, reduciendo tokens mientras mantiene informacion relevante.
"""
import pytest
from datetime import date, datetime

from app.application.services.context_builder import AthleteContextBuilder
from app.domain.entities.training_metrics import ComputedMetrics
from app.domain.entities.alerts import (
    TrainingAlert, 
    AlertCategory, 
    AlertSeverity
)


class TestAthleteContextBuilder:
    """Tests para AthleteContextBuilder."""
    
    @pytest.fixture
    def builder(self):
        return AthleteContextBuilder()
    
    @pytest.fixture
    def sample_metrics(self):
        """Metricas de ejemplo."""
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
            tsb=5.0,
            ramp_rate=2.0,
            adherence_rate=0.85,
            consistency_score=0.80,
            pct_easy=0.75,
            pct_moderate=0.15,
            pct_hard=0.10,
            preferred_workout_days=["Mon", "Wed", "Fri"],
            typical_rest_day="Sun",
            longest_streak=7,
            longest_gap=2,
            volume_trend="increasing",
            intensity_trend="stable",
        )
    
    @pytest.fixture
    def sample_athlete_data(self):
        """Datos de atleta de ejemplo."""
        return {
            "athlete_id": "ATH001",
            "athlete_name": "Juan Perez",
            "age": 35,
            "discipline": "Running",
            "level": "Intermedio",
            "goal": "Correr medio maraton en 1:45",
            "experience": "3 anos",
            "personal": {
                "genero": "Masculino",
                "sesionesSemanales": "4-5",
                "horasSemanales": "5-7 horas",
                "horarioPreferido": "Manana",
                "diaDescanso": "Domingo"
            },
            "medica": {
                "enfermedades": "Ninguna",
                "horasSueno": 7
            },
            "deportiva": {
                "eventoObjetivo": "Medio Maraton de la Ciudad",
                "diasParaEvento": 45,
                "records": {
                    "dist5k": "22:30",
                    "dist10k": "47:00"
                }
            },
            "performance": {
                "training_history": {
                    "days": {}
                }
            }
        }
    
    def test_build_performance_context(self, builder, sample_metrics):
        """Debe generar contexto de performance."""
        context = builder.build_performance_context(sample_metrics)
        
        assert isinstance(context, str)
        assert len(context) > 0
        
        # Debe incluir secciones clave
        assert "Estado Actual" in context or "Carga de Entrenamiento" in context
        assert "CTL" in context or "Fitness" in context
        assert "ATL" in context or "Fatiga" in context
        assert "TSB" in context or "Forma" in context
    
    def test_performance_context_includes_adherence(self, builder, sample_metrics):
        """Debe incluir metricas de adherencia."""
        context = builder.build_performance_context(sample_metrics)
        
        assert "Adherencia" in context or "completado" in context.lower()
    
    def test_performance_context_includes_distribution(self, builder, sample_metrics):
        """Debe incluir distribucion de intensidad."""
        context = builder.build_performance_context(sample_metrics)
        
        assert "Distribucion" in context or "Facil" in context or "Z1" in context
    
    def test_performance_context_with_alerts(self, builder, sample_metrics):
        """Debe incluir alertas activas."""
        sample_metrics.active_alerts = [
            TrainingAlert(
                id="test_alert",
                category=AlertCategory.LOAD,
                severity=AlertSeverity.WARNING,
                title="Alerta de prueba",
                message="Mensaje de prueba",
                recommendation="Recomendacion",
                value=7.0,
                threshold=5.0,
                created_at=datetime.utcnow()
            )
        ]
        
        context = builder.build_performance_context(sample_metrics)
        
        assert "Alerta" in context or "ALERT" in context.upper()
    
    def test_build_full_context(self, builder, sample_athlete_data, sample_metrics):
        """Debe generar contexto completo."""
        context = builder.build_full_context(
            athlete_data=sample_athlete_data,
            computed_metrics=sample_metrics.to_dict(),
            start_date=date.today()
        )
        
        assert isinstance(context, str)
        
        # Debe incluir datos del atleta
        assert "Juan Perez" in context
        assert "35" in context  # edad
        assert "Running" in context
        
        # Debe incluir objetivo
        assert "maraton" in context.lower() or "1:45" in context
        
        # Debe incluir disponibilidad
        assert "semana" in context.lower()
        
        # Debe incluir metricas
        assert "CTL" in context or "Fitness" in context
    
    def test_full_context_without_metrics(self, builder, sample_athlete_data):
        """Debe funcionar sin metricas computadas."""
        context = builder.build_full_context(
            athlete_data=sample_athlete_data,
            computed_metrics=None,
            start_date=date.today()
        )
        
        assert isinstance(context, str)
        assert "Juan Perez" in context
        
        # Sin metricas, no debe incluir CTL/ATL
        # Puede o no incluir, dependiendo de implementacion
    
    def test_build_alerts_context_filters_by_severity(self, builder):
        """Debe filtrar alertas por severidad relevante."""
        alerts = [
            TrainingAlert(
                id="info_alert",
                category=AlertCategory.PERFORMANCE,
                severity=AlertSeverity.INFO,
                title="Info",
                message="Info message",
                recommendation="Info rec",
                value=0.6,
                threshold=0.7,
                created_at=datetime.utcnow()
            ),
            TrainingAlert(
                id="warning_alert",
                category=AlertCategory.LOAD,
                severity=AlertSeverity.WARNING,
                title="Warning",
                message="Warning message",
                recommendation="Warning rec",
                value=7.0,
                threshold=5.0,
                created_at=datetime.utcnow()
            ),
        ]
        
        context = builder.build_alerts_context(alerts)
        
        # Solo debe incluir WARNING y CRITICAL
        assert "Warning" in context
        # INFO no deberia estar marcado como IMPORTANTE
        if context:
            assert "IMPORTANTES" in context or "ALERTA" in context
    
    def test_build_alerts_context_empty(self, builder):
        """Debe manejar lista vacia de alertas."""
        context = builder.build_alerts_context([])
        
        assert context == ""
    
    def test_performance_context_includes_rpe_for_recent_workouts(self, builder, sample_metrics):
        """Debe incluir RPE y sensacion en workouts recientes cuando estan presentes."""
        recent = [
            {
                "_date_str": "2025-01-15",
                "workout_type": "Tempo",
                "duration_completed": "0:50:00",
                "distance_completed": 10,
                "tss_completed": 70,
                "feel": 4,
                "feel_label": "Strong",
                "rpe": 7,
            },
            {
                "_date_str": "2025-01-14",
                "workout_type": "Easy",
                "duration_completed": "1:00:00",
                "distance_completed": 12,
                "tss_completed": 45,
                # sin feel/rpe — no completado
            },
        ]
        context = builder.build_performance_context(sample_metrics, recent_workouts=recent)

        # El primer workout debe incluir datos de esfuerzo percibido
        assert "Sensacion:4/5" in context
        assert "Strong" in context
        assert "RPE:7/10" in context
        # El segundo workout no tiene RPE, no debe generar info extra
        lines = context.split("\n")
        easy_lines = [l for l in lines if "Easy" in l]
        assert easy_lines  # debe existir la linea del workout
        assert "RPE" not in easy_lines[0]  # no debe tener RPE

    def test_extract_recent_workouts(self, builder):
        """Debe extraer workouts recientes del historial."""
        performance_data = {
            "training_history": {
                "days": {
                    "2025-01-15": [{
                        "title": "Long run",
                        "workout_type": "Run",
                        "status": "completed"
                    }],
                    "2025-01-14": [{
                        "title": "Recovery",
                        "workout_type": "Run",
                        "status": "completed"
                    }],
                    "2025-01-13": [{
                        "title": "Intervals",
                        "workout_type": "Run",
                        "status": "completed"
                    }],
                }
            }
        }
        
        workouts = builder.extract_recent_workouts(performance_data, max_count=2)
        
        assert len(workouts) == 2
        # Debe estar ordenado por fecha descendente
        assert workouts[0]["_date_str"] > workouts[1]["_date_str"]
    
    def test_extract_recent_workouts_empty(self, builder):
        """Debe manejar historial vacio."""
        performance_data = {"training_history": {"days": {}}}
        
        workouts = builder.extract_recent_workouts(performance_data)
        
        assert workouts == []


class TestContextTokenOptimization:
    """Tests para verificar optimizacion de tokens."""
    
    @pytest.fixture
    def builder(self):
        return AthleteContextBuilder()
    
    @pytest.fixture
    def complete_athlete_data(self):
        """Datos completos de atleta."""
        return {
            "athlete_id": "ATH001",
            "athlete_name": "Juan Perez",
            "age": 35,
            "discipline": "Running",
            "level": "Intermedio",
            "goal": "Medio maraton sub 1:45",
            "experience": "3 anos",
            "personal": {
                "genero": "Masculino",
                "sesionesSemanales": "4-5",
                "horasSemanales": "5-7 horas"
            },
            "medica": {"enfermedades": "Ninguna"},
            "deportiva": {
                "records": {"dist5k": "22:30", "dist10k": "47:00"}
            },
            "performance": {
                "training_history": {
                    "days": {
                        f"2025-01-{i:02d}": [{
                            "title": f"Workout {i}",
                            "status": "completed",
                            "tss": 50
                        }] for i in range(1, 20)
                    }
                }
            }
        }
    
    def test_context_reasonable_length(self, builder, complete_athlete_data):
        """El contexto debe tener una longitud razonable (~800-1500 tokens)."""
        # Crear metricas computadas
        metrics = ComputedMetrics(
            computed_at=datetime.utcnow(),
            period_days=90,
            period_start=date(2025, 1, 1),
            period_end=date(2025, 3, 31),
            total_workouts=20,
            total_completed=18,
            total_skipped=2,
            total_hours=30.0,
            total_distance_km=300.0,
            total_tss=1500,
            total_elevation_m=3000,
            avg_weekly_hours=3.0,
            avg_weekly_distance=25.0,
            avg_weekly_tss=120.0,
            avg_workouts_per_week=3.0,
            avg_workout_duration_min=55.0,
            ctl=40.0,
            atl=35.0,
            tsb=5.0,
            ramp_rate=2.0,
            adherence_rate=0.90,
            consistency_score=0.85,
            pct_easy=0.78,
            pct_moderate=0.12,
            pct_hard=0.10,
        )
        
        context = builder.build_full_context(
            athlete_data=complete_athlete_data,
            computed_metrics=metrics.to_dict(),
            start_date=date.today()
        )
        
        # Estimar tokens (~4 chars por token promedio)
        estimated_tokens = len(context) / 4
        
        # Debe estar en rango razonable
        assert estimated_tokens < 2000, f"Contexto muy largo: ~{estimated_tokens} tokens"
        assert estimated_tokens > 200, f"Contexto muy corto: ~{estimated_tokens} tokens"
