"""
Tests unitarios para TPDataNormalizer.

Verifica que el normalizador transforma correctamente la estructura
anidada de TrainingPeaks a formato plano, valida datos, y genera
reportes de calidad.
"""
import pytest
from datetime import date, timedelta

from app.application.services.tp_data_normalizer import (
    TPDataNormalizer,
    WorkoutValidationReport,
    HistoryValidationSummary
)


class TestTPDataNormalizer:
    """Tests para TPDataNormalizer."""
    
    @pytest.fixture
    def normalizer(self):
        return TPDataNormalizer()
    
    @pytest.fixture
    def sample_raw_workout(self):
        """
        Workout de ejemplo con estructura real de TrainingPeaks scraping.
        """
        return {
            "date_time": {
                "date": "2025-01-15",
                "time": "06:30"
            },
            "workout_bar": {
                "title": "Easy Run - Base Building",
                "sport": "run",
                "is_locked": False,
                "is_hidden": False,
                "key_stats": {
                    "duration": "1:00:00",
                    "distance": {"value": "10", "units": "km"},
                    "tss": {"value": "45", "units": "TSS"}
                }
            },
            "planned_completed": {
                "duration": {
                    "planned": "1:00:00",
                    "completed": "1:05:23",
                    "units": "h:m:s"
                },
                "distance": {
                    "planned": "10",
                    "completed": "10.5",
                    "units": "km"
                },
                "tss": {
                    "planned": "45",
                    "completed": "52",
                    "units": "TSS"
                },
                "if": {
                    "planned": "0.75",
                    "completed": "0.78",
                    "units": ""
                },
                "elevationGain": {
                    "planned": "100",
                    "completed": "115",
                    "units": "m"
                },
                "calories": {
                    "planned": "500",
                    "completed": "550",
                    "units": "kcal"
                },
                "averagePace": {
                    "planned": "6:00",
                    "completed": "6:12",
                    "units": "min/km"
                }
            },
            "min_avg_max": {
                "heartRate": {
                    "min": "95",
                    "avg": "145",
                    "max": "172",
                    "units": "bpm"
                },
                "cadence": {
                    "min": "160",
                    "avg": "175",
                    "max": "185",
                    "units": "spm"
                },
                "pace": {
                    "min": "5:30",
                    "avg": "6:12",
                    "max": "7:00",
                    "units": "min/km"
                }
            },
            "equipment": {},
            "comments": {
                "pre": "Focus on easy pace",
                "post": "Felt good, slightly faster than planned"
            },
            "workout_details": {
                "description": "Base building run",
                "steps": ["Warmup 10min", "Main run 40min Z2", "Cooldown 10min"]
            }
        }
    
    @pytest.fixture
    def sample_raw_workout_minimal(self):
        """Workout con datos minimos (sin completar)."""
        return {
            "workout_bar": {
                "title": "Planned Intervals",
                "sport": "run"
            },
            "planned_completed": {
                "duration": {
                    "planned": "0:45:00",
                    "completed": None
                },
                "tss": {
                    "planned": "55",
                    "completed": None
                }
            }
        }
    
    @pytest.fixture
    def sample_raw_workout_cycling(self):
        """Workout de ciclismo con power data."""
        return {
            "workout_bar": {
                "title": "Tempo Ride",
                "sport": "bike"
            },
            "planned_completed": {
                "duration": {
                    "planned": "1:30:00",
                    "completed": "1:32:15"
                },
                "distance": {
                    "planned": "40",
                    "completed": "42"
                },
                "tss": {
                    "planned": "80",
                    "completed": "85"
                },
                "if": {
                    "planned": "0.85",
                    "completed": "0.87"
                },
                "normalizedPower": {
                    "planned": "220",
                    "completed": "228"
                }
            },
            "min_avg_max": {
                "power": {
                    "min": "0",
                    "avg": "195",
                    "max": "450"
                },
                "heartRate": {
                    "avg": "155",
                    "max": "178"
                }
            }
        }
    
    def test_normalize_workout_extracts_title(self, normalizer, sample_raw_workout):
        """Debe extraer el titulo correctamente."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout)
        
        assert normalized["title"] == "Easy Run - Base Building"
    
    def test_normalize_workout_extracts_sport(self, normalizer, sample_raw_workout):
        """Debe extraer el deporte correctamente."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout)
        
        assert normalized["sport"] == "run"
    
    def test_normalize_workout_infers_workout_type(self, normalizer, sample_raw_workout):
        """Debe inferir el tipo de workout basado en el titulo."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout)
        
        # "Easy Run" deberia clasificarse como "Easy"
        assert normalized["workout_type"] == "Easy"
    
    def test_normalize_workout_extracts_planned_metrics(self, normalizer, sample_raw_workout):
        """Debe extraer metricas planeadas correctamente."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout)
        
        assert normalized["duration_planned"] == "1:00:00"
        assert normalized["distance_planned"] == 10.0
        assert normalized["tss_planned"] == 45
        assert normalized["if_planned"] == 0.75
    
    def test_normalize_workout_extracts_completed_metrics(self, normalizer, sample_raw_workout):
        """Debe extraer metricas completadas correctamente."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout)
        
        assert normalized["duration_completed"] == "1:05:23"
        assert normalized["distance_completed"] == 10.5
        assert normalized["tss_completed"] == 52
        assert normalized["if_completed"] == 0.78
    
    def test_normalize_workout_extracts_heart_rate(self, normalizer, sample_raw_workout):
        """Debe extraer datos de heart rate correctamente."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout)
        
        assert normalized["hr_avg"] == 145
        assert normalized["hr_max"] == 172
        assert normalized["hr_min"] == 95
    
    def test_normalize_workout_infers_completed_status(self, normalizer, sample_raw_workout):
        """Debe inferir status 'completed' cuando hay datos de ejecucion."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout, "2025-01-15")
        
        assert normalized["status"] == "completed"
    
    def test_normalize_workout_infers_skipped_status(self, normalizer, sample_raw_workout_minimal):
        """Debe inferir status 'skipped' cuando tiene planeado pero no completado y fecha pasada."""
        past_date = (date.today() - timedelta(days=5)).isoformat()
        
        normalized, _ = normalizer.normalize_workout(sample_raw_workout_minimal, past_date)
        
        assert normalized["status"] == "skipped"
    
    def test_normalize_workout_infers_planned_status(self, normalizer, sample_raw_workout_minimal):
        """Debe inferir status 'planned' para workouts futuros sin completar."""
        future_date = (date.today() + timedelta(days=5)).isoformat()
        
        normalized, _ = normalizer.normalize_workout(sample_raw_workout_minimal, future_date)
        
        assert normalized["status"] == "planned"
    
    def test_normalize_workout_extracts_power_data(self, normalizer, sample_raw_workout_cycling):
        """Debe extraer datos de power para ciclismo."""
        normalized, _ = normalizer.normalize_workout(sample_raw_workout_cycling)
        
        assert normalized["normalized_power"] == 228
        assert normalized["avg_power"] == 195
    
    def test_normalize_workout_validates_data(self, normalizer, sample_raw_workout):
        """Debe generar reporte de validacion."""
        _, validation = normalizer.normalize_workout(sample_raw_workout)
        
        assert isinstance(validation, WorkoutValidationReport)
        assert validation.is_valid is True
        assert validation.data_quality_score > 0.5
    
    def test_normalize_workout_detects_invalid_tss(self, normalizer):
        """Debe detectar TSS invalido."""
        invalid_workout = {
            "workout_bar": {"title": "Test"},
            "planned_completed": {
                "tss": {"completed": "999"}  # TSS muy alto
            }
        }
        
        _, validation = normalizer.normalize_workout(invalid_workout)
        
        assert validation.is_valid is False
        assert any("TSS" in issue for issue in validation.issues)
    
    def test_normalize_workout_detects_invalid_hr(self, normalizer):
        """Debe detectar HR invalido."""
        invalid_workout = {
            "workout_bar": {"title": "Test"},
            "min_avg_max": {
                "heartRate": {"avg": "300"}  # HR imposible
            }
        }
        
        _, validation = normalizer.normalize_workout(invalid_workout)
        
        assert validation.is_valid is False
        assert any("HR" in issue for issue in validation.issues)
    
    def test_normalize_workout_warns_on_unusual_if(self, normalizer):
        """Debe advertir sobre IF inusual."""
        unusual_workout = {
            "workout_bar": {"title": "Test"},
            "planned_completed": {
                "if": {"completed": "1.6"}  # IF muy alto pero posible
            }
        }
        
        _, validation = normalizer.normalize_workout(unusual_workout)
        
        # Debe ser warning, no error
        assert any("IF" in warning for warning in validation.warnings)
    
    def test_normalize_workout_calculates_quality_score(self, normalizer, sample_raw_workout):
        """Debe calcular score de calidad alto para workout completo."""
        normalized, validation = normalizer.normalize_workout(sample_raw_workout)
        
        # Workout completo deberia tener score alto
        assert validation.data_quality_score >= 0.7
    
    def test_normalize_workout_low_quality_for_minimal_data(self, normalizer):
        """Debe calcular score bajo para workout con pocos datos."""
        minimal_workout = {
            "workout_bar": {"title": "Empty workout"}
        }
        
        _, validation = normalizer.normalize_workout(minimal_workout)
        
        assert validation.data_quality_score < 0.3


class TestNormalizeHistory:
    """Tests para normalizacion de historial completo."""
    
    @pytest.fixture
    def normalizer(self):
        return TPDataNormalizer()
    
    @pytest.fixture
    def sample_history(self):
        """Historial de ejemplo con varios dias."""
        return {
            "2025-01-15": [{
                "workout_bar": {"title": "Easy Run", "sport": "run"},
                "planned_completed": {
                    "duration": {"completed": "1:00:00"},
                    "tss": {"completed": "50"}
                },
                "min_avg_max": {
                    "heartRate": {"avg": "140"}
                }
            }],
            "2025-01-16": [{
                "workout_bar": {"title": "Intervals", "sport": "run"},
                "planned_completed": {
                    "duration": {"completed": "0:45:00"},
                    "tss": {"completed": "65"},
                    "if": {"completed": "0.92"}
                }
            }],
            "2025-01-17": [{
                "workout_bar": {"title": "Rest Day"},
                "planned_completed": {}
            }]
        }
    
    def test_normalize_history_returns_normalized_days(self, normalizer, sample_history):
        """Debe retornar diccionario de dias normalizados."""
        normalized_days, _ = normalizer.normalize_history(sample_history)
        
        assert isinstance(normalized_days, dict)
        assert "2025-01-15" in normalized_days
        assert "2025-01-16" in normalized_days
    
    def test_normalize_history_returns_summary(self, normalizer, sample_history):
        """Debe retornar resumen de validacion."""
        _, summary = normalizer.normalize_history(sample_history)
        
        assert isinstance(summary, HistoryValidationSummary)
        assert summary.total_workouts == 3
    
    def test_normalize_history_counts_by_status(self, normalizer, sample_history):
        """Debe contar workouts por status."""
        _, summary = normalizer.normalize_history(sample_history)
        
        assert "completed" in summary.workouts_by_status
        assert summary.workouts_by_status["completed"] >= 1
    
    def test_normalize_history_calculates_avg_quality(self, normalizer, sample_history):
        """Debe calcular calidad promedio."""
        _, summary = normalizer.normalize_history(sample_history)
        
        assert 0 <= summary.avg_quality_score <= 1
    
    def test_normalize_history_empty_input(self, normalizer):
        """Debe manejar historial vacio."""
        normalized_days, summary = normalizer.normalize_history({})
        
        assert normalized_days == {}
        assert summary.total_workouts == 0


class TestParsingHelpers:
    """Tests para metodos de parsing."""
    
    @pytest.fixture
    def normalizer(self):
        return TPDataNormalizer()
    
    def test_parse_float_from_string(self, normalizer):
        """Debe parsear float desde string."""
        assert normalizer._parse_float("10.5") == 10.5
    
    def test_parse_float_from_int(self, normalizer):
        """Debe parsear float desde int."""
        assert normalizer._parse_float(10) == 10.0
    
    def test_parse_float_with_units(self, normalizer):
        """Debe remover unidades al parsear."""
        assert normalizer._parse_float("10.5km") == 10.5
        assert normalizer._parse_float("75%") == 75.0
    
    def test_parse_float_none(self, normalizer):
        """Debe retornar None para valores invalidos."""
        assert normalizer._parse_float(None) is None
        assert normalizer._parse_float("") is None
        assert normalizer._parse_float("invalid") is None
    
    def test_parse_int(self, normalizer):
        """Debe parsear int correctamente."""
        assert normalizer._parse_int("45") == 45
        assert normalizer._parse_int(45.6) == 46  # Redondea
    
    def test_extract_nested(self, normalizer):
        """Debe extraer valores de estructuras anidadas."""
        data = {
            "level1": {
                "level2": {
                    "value": "found"
                }
            }
        }
        
        assert normalizer._extract_nested(data, "level1", "level2", "value") == "found"
        assert normalizer._extract_nested(data, "level1", "missing") is None
    
    def test_infer_workout_type_easy(self, normalizer):
        """Debe inferir tipo Easy correctamente."""
        assert normalizer._infer_workout_type("Easy Run Z2", "run") == "Easy"
        assert normalizer._infer_workout_type("Rodaje suave", "run") == "Easy"
    
    def test_infer_workout_type_intervals(self, normalizer):
        """Debe inferir tipo Intervals correctamente."""
        assert normalizer._infer_workout_type("VO2max Intervals", "run") == "Intervals"
        assert normalizer._infer_workout_type("Series 5x1000", "run") == "Intervals"
    
    def test_infer_workout_type_long(self, normalizer):
        """Debe inferir tipo Long correctamente."""
        assert normalizer._infer_workout_type("Long Run 25k", "run") == "Long"
        assert normalizer._infer_workout_type("Rodaje largo", "run") == "Long"
    
    def test_is_valid_duration(self, normalizer):
        """Debe validar formatos de duracion."""
        assert normalizer._is_valid_duration("1:30:00") is True
        assert normalizer._is_valid_duration("45:00") is True
        assert normalizer._is_valid_duration("1:05:23") is True
        assert normalizer._is_valid_duration("invalid") is False
