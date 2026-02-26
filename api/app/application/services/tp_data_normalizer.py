"""
Normalizador de datos de TrainingPeaks.

Transforma la estructura anidada del scraping de TrainingPeaks
a un formato plano optimizado para el HistoryProcessor.

Resuelve el problema de desalineacion entre:
- Estructura del scraping: anidada (planned_completed.tss.completed)
- Estructura esperada: plana (tss_completed)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple, Set

from loguru import logger


@dataclass
class WorkoutValidationReport:
    """
    Reporte de validacion para un workout individual.
    
    Incluye informacion sobre la calidad de los datos
    y problemas encontrados durante la normalizacion.
    """
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data_quality_score: float = 0.0
    fields_present: Set[str] = field(default_factory=set)
    fields_missing: Set[str] = field(default_factory=set)


@dataclass
class HistoryValidationSummary:
    """
    Resumen de validacion para todo el historial.
    """
    total_workouts: int = 0
    valid_workouts: int = 0
    invalid_workouts: int = 0
    avg_quality_score: float = 0.0
    total_issues: int = 0
    total_warnings: int = 0
    workouts_by_status: Dict[str, int] = field(default_factory=dict)


class TPDataNormalizer:
    """
    Normalizador de datos de TrainingPeaks.
    
    Convierte la estructura anidada del scraping a formato plano
    y valida los datos en el proceso.
    
    Uso:
        normalizer = TPDataNormalizer()
        normalized_days, summary = normalizer.normalize_history(raw_days)
    """
    
    # Rangos validos para validacion
    VALID_TSS_RANGE = (0, 500)
    VALID_IF_RANGE = (0.4, 1.5)
    VALID_HR_RANGE = (40, 220)
    VALID_DISTANCE_RANGE = (0, 500)  # km
    
    # Campos requeridos para calculos
    REQUIRED_FIELDS = {"tss_completed", "duration_completed"}
    OPTIONAL_FIELDS = {"if_completed", "hr_avg", "distance_completed"}
    
    def normalize_history(
        self, 
        raw_days: Dict[str, List[Dict]]
    ) -> Tuple[Dict[str, List[Dict]], HistoryValidationSummary]:
        """
        Normaliza todo el historial de entrenamientos.
        
        Args:
            raw_days: Diccionario con fecha ISO como key y lista de workouts raw
            
        Returns:
            Tuple de (dias normalizados, resumen de validacion)
        """
        normalized_days: Dict[str, List[Dict]] = {}
        summary = HistoryValidationSummary()
        quality_scores: List[float] = []
        
        for date_str, workouts in raw_days.items():
            normalized_workouts = []
            
            for raw_workout in workouts:
                normalized, validation = self.normalize_workout(raw_workout, date_str)
                normalized_workouts.append(normalized)
                
                # Actualizar estadisticas
                summary.total_workouts += 1
                if validation.is_valid:
                    summary.valid_workouts += 1
                else:
                    summary.invalid_workouts += 1
                
                quality_scores.append(validation.data_quality_score)
                summary.total_issues += len(validation.issues)
                summary.total_warnings += len(validation.warnings)
                
                # Contar por status
                status = normalized.get("status", "unknown")
                summary.workouts_by_status[status] = (
                    summary.workouts_by_status.get(status, 0) + 1
                )
            
            if normalized_workouts:
                normalized_days[date_str] = normalized_workouts
        
        # Calcular promedio de calidad
        if quality_scores:
            summary.avg_quality_score = sum(quality_scores) / len(quality_scores)
        
        logger.info(
            f"Historial normalizado: {summary.total_workouts} workouts, "
            f"{summary.valid_workouts} validos, "
            f"calidad promedio: {summary.avg_quality_score:.0%}"
        )
        
        return normalized_days, summary
    
    def normalize_workout(
        self, 
        raw: Dict[str, Any],
        date_str: Optional[str] = None
    ) -> Tuple[Dict[str, Any], WorkoutValidationReport]:
        """
        Normaliza un workout individual de estructura anidada a plana.
        
        Args:
            raw: Datos raw del workout desde el scraping
            date_str: Fecha del workout en formato ISO (opcional)
            
        Returns:
            Tuple de (workout normalizado, reporte de validacion)
        """
        validation = WorkoutValidationReport(is_valid=True)
        
        # Extraer datos de las diferentes secciones
        workout_bar = raw.get("workout_bar") or {}
        planned_completed = raw.get("planned_completed") or {}
        min_avg_max = raw.get("min_avg_max") or {}
        date_time = raw.get("date_time") or {}
        
        # --- Identificacion ---
        title = self._extract_title(workout_bar, raw)
        sport = self._extract_sport(workout_bar, raw)
        workout_type = self._infer_workout_type(title, sport)
        
        # --- Metricas planeadas ---
        duration_planned = self._extract_nested(
            planned_completed, "duration", "planned"
        )
        distance_planned = self._parse_float(
            self._extract_nested(planned_completed, "distance", "planned")
        )
        tss_planned = self._parse_int(
            self._extract_nested(planned_completed, "tss", "planned")
        )
        if_planned = self._parse_float(
            self._extract_nested(planned_completed, "if", "planned")
        )
        
        # --- Metricas completadas ---
        duration_completed = self._extract_nested(
            planned_completed, "duration", "completed"
        )
        distance_completed = self._parse_float(
            self._extract_nested(planned_completed, "distance", "completed")
        )
        tss_completed = self._parse_int(
            self._extract_nested(planned_completed, "tss", "completed")
        )
        if_completed = self._parse_float(
            self._extract_nested(planned_completed, "if", "completed")
        )
        
        # --- Heart Rate ---
        hr_avg = self._parse_int(
            self._extract_nested(min_avg_max, "heartRate", "avg")
        )
        hr_max = self._parse_int(
            self._extract_nested(min_avg_max, "heartRate", "max")
        )
        hr_min = self._parse_int(
            self._extract_nested(min_avg_max, "heartRate", "min")
        )
        
        # --- Otros datos ---
        elevation_gain = self._parse_int(
            self._extract_nested(planned_completed, "elevationGain", "completed")
        )
        calories = self._parse_int(
            self._extract_nested(planned_completed, "calories", "completed")
        )
        normalized_power = self._parse_int(
            self._extract_nested(planned_completed, "normalizedPower", "completed")
        )
        avg_power = self._parse_int(
            self._extract_nested(min_avg_max, "power", "avg")
        )
        avg_pace = self._extract_nested(planned_completed, "averagePace", "completed")
        avg_speed = self._parse_float(
            self._extract_nested(planned_completed, "averageSpeed", "completed")
        )
        
        # --- Esfuerzo percibido (solo workouts completados) ---
        perceived = raw.get("perceived_exertion") or {}
        feel = self._parse_int(perceived.get("feel_value"))   # 1-5 or None
        feel_label = perceived.get("feel_label") or None      # "Very Strong", etc.
        rpe = self._parse_int(perceived.get("rpe_value"))     # 0-10 or None
        
        # --- Inferir estado ---
        status = self._infer_status(
            duration_completed=duration_completed,
            tss_completed=tss_completed,
            hr_avg=hr_avg,
            duration_planned=duration_planned,
            date_str=date_str
        )
        
        # --- Validar datos ---
        self._validate_workout(
            validation=validation,
            tss_completed=tss_completed,
            tss_planned=tss_planned,
            if_completed=if_completed,
            if_planned=if_planned,
            hr_avg=hr_avg,
            hr_max=hr_max,
            distance_completed=distance_completed,
            duration_completed=duration_completed,
            feel=feel,
            rpe=rpe,
        )
        
        # --- Calcular score de calidad ---
        validation.data_quality_score = self._calculate_quality_score(
            validation=validation,
            tss_completed=tss_completed,
            duration_completed=duration_completed,
            if_completed=if_completed,
            hr_avg=hr_avg,
            status=status
        )
        
        # Construir workout normalizado
        normalized = {
            # Identificacion
            "title": title,
            "sport": sport,
            "workout_type": workout_type,
            
            # Estado
            "status": status,
            
            # Metricas planeadas
            "duration_planned": duration_planned,
            "distance_planned": distance_planned,
            "tss_planned": tss_planned,
            "if_planned": if_planned,
            
            # Metricas completadas
            "duration_completed": duration_completed,
            "distance_completed": distance_completed,
            "tss_completed": tss_completed,
            "if_completed": if_completed,
            
            # Heart Rate
            "hr_avg": hr_avg,
            "hr_max": hr_max,
            "hr_min": hr_min,
            
            # Power (ciclismo)
            "normalized_power": normalized_power,
            "avg_power": avg_power,
            
            # Otros
            "elevation_gain": elevation_gain,
            "calories": calories,
            "avg_pace": avg_pace,
            "avg_speed": avg_speed,
            
            # Esfuerzo percibido (solo completados)
            "feel": feel,             # 1-5 (How did you feel?) or None
            "feel_label": feel_label, # e.g. "Very Strong", "Normal", or None
            "rpe": rpe,               # 0-10 (Rating of Perceived Exertion) or None
            
            # Metadata
            "_validation": {
                "is_valid": validation.is_valid,
                "issues": validation.issues,
                "warnings": validation.warnings,
                "data_quality_score": validation.data_quality_score
            }
        }
        
        # Log si hay problemas significativos
        if validation.issues:
            logger.debug(
                f"Workout '{title}' normalizado con issues: {validation.issues}"
            )
        
        return normalized, validation
    
    # --- Metodos de extraccion ---
    
    def _extract_nested(
        self, 
        data: Dict, 
        *keys: str, 
        default: Any = None
    ) -> Any:
        """
        Extrae valor de estructura anidada de forma segura.
        
        Ejemplo: _extract_nested(data, "tss", "completed") 
                 equivale a data.get("tss", {}).get("completed")
        """
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key, default)
            if current is None:
                return default
        return current
    
    def _extract_title(self, workout_bar: Dict, raw: Dict) -> str:
        """Extrae el titulo del workout."""
        title = (
            workout_bar.get("title") or
            raw.get("title") or
            raw.get("workout_title") or
            "Sin titulo"
        )
        return str(title).strip()
    
    def _extract_sport(self, workout_bar: Dict, raw: Dict) -> str:
        """Extrae el deporte/disciplina."""
        sport = (
            workout_bar.get("sport") or
            raw.get("sport") or
            raw.get("activity_type") or
            "unknown"
        )
        return str(sport).lower().strip()
    
    def _infer_workout_type(self, title: str, sport: str) -> str:
        """
        Infiere el tipo de workout basado en el titulo.
        
        Categorias: Easy, Tempo, Intervals, Long, Recovery, Strength, Day off
        """
        title_lower = title.lower()
        
        # Patrones comunes
        if any(k in title_lower for k in ["easy", "facil", "suave", "z2"]):
            return "Easy"
        if any(k in title_lower for k in ["tempo", "threshold", "umbral"]):
            return "Tempo"
        if any(k in title_lower for k in ["interval", "series", "fartlek", "vo2"]):
            return "Intervals"
        if any(k in title_lower for k in ["long", "largo", "lsd"]):
            return "Long"
        if any(k in title_lower for k in ["recovery", "recupera", "rest"]):
            return "Recovery"
        if any(k in title_lower for k in ["strength", "fuerza", "gym", "core"]):
            return "Strength"
        if any(k in title_lower for k in ["off", "descanso", "libre"]):
            return "Day off"
        
        return "General"
    
    # --- Metodos de parsing ---
    
    def _parse_float(self, value: Any) -> Optional[float]:
        """Parsea valor a float de forma segura."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        
        try:
            # Limpiar string
            clean = str(value).strip()
            if not clean:
                return None
            
            # Remover unidades comunes
            clean = re.sub(r'[a-zA-Z%]+$', '', clean).strip()
            clean = clean.replace(',', '.')
            
            return float(clean)
        except (ValueError, TypeError):
            return None
    
    def _parse_int(self, value: Any) -> Optional[int]:
        """Parsea valor a int de forma segura."""
        float_val = self._parse_float(value)
        if float_val is None:
            return None
        return int(round(float_val))
    
    # --- Inferencia de estado ---
    
    def _infer_status(
        self,
        duration_completed: Optional[str],
        tss_completed: Optional[int],
        hr_avg: Optional[int],
        duration_planned: Optional[str],
        date_str: Optional[str]
    ) -> str:
        """
        Infiere el estado del workout.
        
        Returns:
            "completed" - Si tiene datos de ejecucion
            "skipped" - Si tiene planeado pero no ejecutado y fecha pasada
            "planned" - Si solo tiene datos planeados
        """
        # Tiene datos de ejecucion?
        has_completed_data = any([
            duration_completed and duration_completed.strip(),
            tss_completed and tss_completed > 0,
            hr_avg and hr_avg > 0
        ])
        
        if has_completed_data:
            return "completed"
        
        # Tiene datos planeados?
        has_planned_data = any([
            duration_planned and duration_planned.strip()
        ])
        
        if has_planned_data:
            # Verificar si la fecha ya paso
            if date_str:
                try:
                    workout_date = date.fromisoformat(date_str)
                    if workout_date < date.today():
                        return "skipped"
                except ValueError:
                    pass
            return "planned"
        
        return "unknown"
    
    # --- Validacion ---
    
    def _validate_workout(
        self,
        validation: WorkoutValidationReport,
        tss_completed: Optional[int],
        tss_planned: Optional[int],
        if_completed: Optional[float],
        if_planned: Optional[float],
        hr_avg: Optional[int],
        hr_max: Optional[int],
        distance_completed: Optional[float],
        duration_completed: Optional[str],
        feel: Optional[int] = None,
        rpe: Optional[int] = None,
    ) -> None:
        """Valida los datos del workout y actualiza el reporte."""
        
        # Validar TSS
        for tss, name in [(tss_completed, "TSS completado"), (tss_planned, "TSS planeado")]:
            if tss is not None:
                validation.fields_present.add(name)
                if not (self.VALID_TSS_RANGE[0] <= tss <= self.VALID_TSS_RANGE[1]):
                    validation.issues.append(f"{name} fuera de rango: {tss}")
                    validation.is_valid = False
            else:
                validation.fields_missing.add(name)
        
        # Validar IF
        for if_val, name in [(if_completed, "IF completado"), (if_planned, "IF planeado")]:
            if if_val is not None:
                validation.fields_present.add(name)
                if not (self.VALID_IF_RANGE[0] <= if_val <= self.VALID_IF_RANGE[1]):
                    validation.warnings.append(f"{name} fuera de rango tipico: {if_val}")
            else:
                validation.fields_missing.add(name)
        
        # Validar HR
        if hr_avg is not None:
            validation.fields_present.add("HR promedio")
            if not (self.VALID_HR_RANGE[0] <= hr_avg <= self.VALID_HR_RANGE[1]):
                validation.issues.append(f"HR promedio fuera de rango: {hr_avg}")
                validation.is_valid = False
        else:
            validation.fields_missing.add("HR promedio")
        
        if hr_max is not None:
            validation.fields_present.add("HR maximo")
            if hr_avg and hr_max < hr_avg:
                validation.warnings.append(f"HR max ({hr_max}) menor que HR avg ({hr_avg})")
        
        # Validar distancia
        if distance_completed is not None:
            validation.fields_present.add("Distancia")
            if not (self.VALID_DISTANCE_RANGE[0] <= distance_completed <= self.VALID_DISTANCE_RANGE[1]):
                validation.warnings.append(f"Distancia inusual: {distance_completed} km")
        
        # Validar duracion
        if duration_completed:
            validation.fields_present.add("Duracion")
            if not self._is_valid_duration(duration_completed):
                validation.warnings.append(f"Formato de duracion inusual: {duration_completed}")
        
        # Validar feel (How did you feel?) — rango 1-5
        if feel is not None:
            validation.fields_present.add("Feel")
            if not (1 <= feel <= 5):
                validation.warnings.append(f"Feel fuera de rango (1-5): {feel}")
        
        # Validar RPE — rango 0-10
        if rpe is not None:
            validation.fields_present.add("RPE")
            if not (0 <= rpe <= 10):
                validation.warnings.append(f"RPE fuera de rango (0-10): {rpe}")
    
    def _is_valid_duration(self, duration: str) -> bool:
        """Verifica si el formato de duracion es valido (h:mm:ss o mm:ss)."""
        if not duration:
            return False
        
        # Patrones validos: "1:30:00", "45:00", "1:05:23"
        pattern = r'^(\d+:)?\d{1,2}:\d{2}$'
        return bool(re.match(pattern, duration.strip()))
    
    def _calculate_quality_score(
        self,
        validation: WorkoutValidationReport,
        tss_completed: Optional[int],
        duration_completed: Optional[str],
        if_completed: Optional[float],
        hr_avg: Optional[int],
        status: str
    ) -> float:
        """
        Calcula un score de calidad de 0.0 a 1.0.
        
        Factores:
        - Campos presentes: +0.2 por campo clave
        - Validacion pasada: +0.2
        - Status completado: +0.1
        """
        score = 0.0
        
        # Campos clave presentes
        if tss_completed is not None and tss_completed > 0:
            score += 0.25
        if duration_completed and duration_completed.strip():
            score += 0.20
        if if_completed is not None:
            score += 0.20
        if hr_avg is not None and hr_avg > 0:
            score += 0.15
        
        # Bonus por validacion limpia
        if validation.is_valid and not validation.issues:
            score += 0.10
        
        # Bonus por status completado
        if status == "completed":
            score += 0.10
        
        return min(score, 1.0)
