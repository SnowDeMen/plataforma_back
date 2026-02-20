"""
Procesador de historial de entrenamientos.

Calcula metricas computadas a partir del historial raw de TrainingPeaks.
Implementa el modelo Banister para CTL/ATL/TSB y otras metricas
de rendimiento y adherencia.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from loguru import logger

from app.domain.entities.training_metrics import ComputedMetrics
from app.domain.entities.alerts import AlertRegistry, TrainingAlert


class HistoryProcessor:
    """
    Procesador de historial de entrenamientos.
    
    Convierte datos raw del historial de TrainingPeaks en metricas
    estructuradas optimizadas para el LLM.
    
    Uso:
        processor = HistoryProcessor()
        metrics = processor.process(raw_history_days, period_days=90)
    """
    
    # Constantes del modelo Banister
    CTL_TIME_CONSTANT = 42  # dias para Chronic Training Load
    ATL_TIME_CONSTANT = 7   # dias para Acute Training Load
    
    # Umbrales de intensidad (basados en Intensity Factor)
    IF_EASY_THRESHOLD = 0.75      # Z1-Z2
    IF_MODERATE_THRESHOLD = 0.90  # Z3
    
    # Dias de la semana para patrones
    DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    def process(
        self, 
        raw_days: Dict[str, List[Dict]], 
        period_days: int = 90
    ) -> ComputedMetrics:
        """
        Procesa el historial raw y genera metricas computadas.
        
        Args:
            raw_days: Diccionario con fecha ISO como key y lista de workouts como value
                      Estructura: {"2025-01-15": [{"title": "...", "tss": 50, ...}, ...]}
            period_days: Numero de dias hacia atras a analizar (default: 90)
            
        Returns:
            ComputedMetrics con todas las metricas calculadas
        """
        today = date.today()
        period_start = today - timedelta(days=period_days)
        
        # Filtrar workouts dentro del periodo
        workouts = self._flatten_and_filter(raw_days, period_start, today)
        
        if not workouts:
            logger.warning("No hay workouts en el periodo para procesar")
            return self._empty_metrics(today, period_start, period_days)
        
        # Calcular metricas
        totals = self._calculate_totals(workouts)
        averages = self._calculate_averages(workouts, period_days)
        load_metrics = self._calculate_load_metrics(workouts, today)
        adherence = self._calculate_adherence(workouts)
        distribution = self._calculate_intensity_distribution(workouts)
        patterns = self._calculate_patterns(workouts)
        trends = self._calculate_trends(workouts, today)
        type_distribution = self._calculate_type_distribution(workouts)
        
        metrics = ComputedMetrics(
            computed_at=datetime.utcnow(),
            period_days=period_days,
            period_start=period_start,
            period_end=today,
            
            # Totales
            total_workouts=totals["total_workouts"],
            total_completed=totals["total_completed"],
            total_skipped=totals["total_skipped"],
            total_hours=totals["total_hours"],
            total_distance_km=totals["total_distance_km"],
            total_tss=totals["total_tss"],
            total_elevation_m=totals["total_elevation_m"],
            
            # Promedios
            avg_weekly_hours=averages["weekly_hours"],
            avg_weekly_distance=averages["weekly_distance"],
            avg_weekly_tss=averages["weekly_tss"],
            avg_workouts_per_week=averages["workouts_per_week"],
            avg_workout_duration_min=averages["workout_duration_min"],
            
            # Carga
            ctl=load_metrics["ctl"],
            atl=load_metrics["atl"],
            tsb=load_metrics["tsb"],
            ramp_rate=load_metrics["ramp_rate"],
            
            # Adherencia
            adherence_rate=adherence["rate"],
            consistency_score=adherence["consistency"],
            
            # Distribucion intensidad
            pct_easy=distribution["easy"],
            pct_moderate=distribution["moderate"],
            pct_hard=distribution["hard"],
            
            # Patrones
            preferred_workout_days=patterns["preferred_days"],
            typical_rest_day=patterns["rest_day"],
            longest_streak=patterns["longest_streak"],
            longest_gap=patterns["longest_gap"],
            
            # Tendencias
            volume_trend=trends["volume"],
            intensity_trend=trends["intensity"],
            
            # Distribucion por tipo
            distribution_by_type=type_distribution,
        )
        
        # Evaluar alertas
        alerts = AlertRegistry.evaluate_all(metrics)
        metrics.active_alerts = alerts
        
        logger.info(
            f"Metricas procesadas: {totals['total_workouts']} workouts, "
            f"CTL={load_metrics['ctl']:.1f}, ATL={load_metrics['atl']:.1f}, "
            f"TSB={load_metrics['tsb']:.1f}, alertas={len(alerts)}"
        )
        
        return metrics
    
    def _flatten_and_filter(
        self, 
        raw_days: Dict[str, List[Dict]], 
        start: date, 
        end: date
    ) -> List[Dict]:
        """
        Aplana el diccionario de dias y filtra por periodo.
        Agrega la fecha a cada workout.
        
        IMPORTANTE: Hace copia de cada workout para no mutar los originales.
        Esto evita que objetos date se filtren a datos que se guardan en JSON.
        """
        workouts = []
        
        for date_str, day_workouts in raw_days.items():
            try:
                workout_date = date.fromisoformat(date_str)
            except ValueError:
                continue
            
            if start <= workout_date <= end:
                for w in day_workouts:
                    # Copia para no mutar el original (evita bug de serializacion JSON)
                    workout_copy = w.copy()
                    workout_copy["_date"] = workout_date
                    workout_copy["_date_str"] = date_str
                    workouts.append(workout_copy)
        
        # Ordenar por fecha
        workouts.sort(key=lambda w: w["_date"])
        return workouts
    
    def _calculate_totals(self, workouts: List[Dict]) -> Dict[str, Any]:
        """Calcula totales del periodo."""
        total_workouts = len(workouts)
        total_completed = 0
        total_skipped = 0
        total_hours = 0.0
        total_distance = 0.0
        total_tss = 0
        total_elevation = 0
        
        for w in workouts:
            # Determinar estado del workout
            is_completed = self._is_completed(w)
            if is_completed:
                total_completed += 1
            elif self._is_skipped(w):
                total_skipped += 1
            
            # Solo sumar metricas de workouts completados
            if is_completed:
                total_hours += self._parse_duration_hours(w)
                total_distance += self._parse_distance(w)
                total_tss += self._parse_tss(w)
                total_elevation += self._parse_elevation(w)
        
        return {
            "total_workouts": total_workouts,
            "total_completed": total_completed,
            "total_skipped": total_skipped,
            "total_hours": round(total_hours, 1),
            "total_distance_km": round(total_distance, 1),
            "total_tss": total_tss,
            "total_elevation_m": total_elevation,
        }
    
    def _calculate_averages(self, workouts: List[Dict], period_days: int) -> Dict[str, float]:
        """Calcula promedios semanales."""
        weeks = period_days / 7
        if weeks == 0:
            weeks = 1
        
        totals = self._calculate_totals(workouts)
        
        completed_workouts = [w for w in workouts if self._is_completed(w)]
        avg_duration = 0.0
        if completed_workouts:
            durations = [self._parse_duration_hours(w) * 60 for w in completed_workouts]
            avg_duration = sum(durations) / len(durations)
        
        return {
            "weekly_hours": round(totals["total_hours"] / weeks, 1),
            "weekly_distance": round(totals["total_distance_km"] / weeks, 1),
            "weekly_tss": round(totals["total_tss"] / weeks, 1),
            "workouts_per_week": round(totals["total_completed"] / weeks, 1),
            "workout_duration_min": round(avg_duration, 0),
        }
    
    def _calculate_load_metrics(self, workouts: List[Dict], today: date) -> Dict[str, float]:
        """
        Calcula metricas de carga usando el modelo Banister.
        
        CTL (Chronic Training Load): Promedio ponderado exponencial de TSS (42 dias)
        ATL (Acute Training Load): Promedio ponderado exponencial de TSS (7 dias)
        TSB (Training Stress Balance): CTL - ATL
        Ramp Rate: Cambio semanal de CTL
        """
        # Crear diccionario de TSS por dia
        tss_by_day: Dict[date, int] = {}
        for w in workouts:
            if self._is_completed(w):
                d = w["_date"]
                tss = self._parse_tss(w)
                tss_by_day[d] = tss_by_day.get(d, 0) + tss
        
        # Calcular CTL y ATL usando EWMA
        ctl = self._calculate_ewma(tss_by_day, today, self.CTL_TIME_CONSTANT)
        atl = self._calculate_ewma(tss_by_day, today, self.ATL_TIME_CONSTANT)
        tsb = ctl - atl
        
        # Calcular ramp rate (cambio de CTL en la ultima semana)
        ctl_week_ago = self._calculate_ewma(
            tss_by_day, 
            today - timedelta(days=7), 
            self.CTL_TIME_CONSTANT
        )
        ramp_rate = (ctl - ctl_week_ago) / 7 if ctl_week_ago > 0 else 0
        
        return {
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
            "ramp_rate": round(ramp_rate, 2),
        }
    
    def _calculate_ewma(
        self, 
        tss_by_day: Dict[date, int], 
        reference_date: date, 
        time_constant: int
    ) -> float:
        """
        Calcula Exponentially Weighted Moving Average para TSS.
        
        Formula: EWMA = sum(TSS_i * decay^(dias_desde_referencia)) / time_constant
        """
        if not tss_by_day:
            return 0.0
        
        decay = math.exp(-1 / time_constant)
        weighted_sum = 0.0
        
        for workout_date, tss in tss_by_day.items():
            days_ago = (reference_date - workout_date).days
            if days_ago >= 0 and days_ago <= time_constant * 2:
                weight = decay ** days_ago
                weighted_sum += tss * weight
        
        return weighted_sum / time_constant
    
    def _calculate_adherence(self, workouts: List[Dict]) -> Dict[str, float]:
        """
        Calcula metricas de adherencia al plan.
        """
        if not workouts:
            return {"rate": 0.0, "consistency": 0.0}
        
        total = len(workouts)
        completed = sum(1 for w in workouts if self._is_completed(w))
        rate = completed / total if total > 0 else 0.0
        
        # Consistency: que tan regular es el atleta
        # Calculamos varianza de dias entre entrenamientos
        completed_dates = sorted(set(w["_date"] for w in workouts if self._is_completed(w)))
        
        if len(completed_dates) < 2:
            consistency = 0.5
        else:
            gaps = [(completed_dates[i+1] - completed_dates[i]).days 
                    for i in range(len(completed_dates) - 1)]
            avg_gap = sum(gaps) / len(gaps)
            variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)
            # Normalizar: baja varianza = alta consistencia
            consistency = 1 / (1 + variance / 10)
        
        return {
            "rate": round(rate, 2),
            "consistency": round(consistency, 2),
        }
    
    def _calculate_intensity_distribution(self, workouts: List[Dict]) -> Dict[str, float]:
        """
        Calcula distribucion de intensidad usando clasificacion robusta.
        
        Usa multiples senales: IF, HR, TSS/hora.
        Regla 80/20: idealmente 80% facil, 20% moderado/intenso.
        """
        completed = [w for w in workouts if self._is_completed(w)]
        
        if not completed:
            return {"easy": 0.0, "moderate": 0.0, "hard": 0.0}
        
        easy = 0
        moderate = 0
        hard = 0
        low_confidence_count = 0
        
        for w in completed:
            zone, confidence = self._classify_intensity_robust(w)
            
            if confidence < 0.3:
                low_confidence_count += 1
            
            if zone == "easy":
                easy += 1
            elif zone == "moderate":
                moderate += 1
            else:
                hard += 1
        
        total = len(completed)
        
        # Log si hay muchos workouts con baja confianza
        if low_confidence_count > total * 0.3:
            logger.warning(
                f"Distribucion de intensidad: {low_confidence_count}/{total} workouts "
                f"clasificados con baja confianza (faltan datos de IF/HR)"
            )
        
        return {
            "easy": round(easy / total, 2),
            "moderate": round(moderate / total, 2),
            "hard": round(hard / total, 2),
        }
    
    def _calculate_patterns(self, workouts: List[Dict]) -> Dict[str, Any]:
        """
        Detecta patrones de entrenamiento del atleta.
        """
        completed = [w for w in workouts if self._is_completed(w)]
        
        # Dias preferidos
        day_counts = Counter(w["_date"].strftime("%a") for w in completed)
        preferred_days = [day for day, _ in day_counts.most_common(3)]
        
        # Dia de descanso tipico
        all_days_set = set(self.DAYS_OF_WEEK)
        workout_days_set = set(day_counts.keys())
        rest_days = all_days_set - workout_days_set
        rest_day = list(rest_days)[0] if rest_days else None
        
        # Streaks
        longest_streak, longest_gap = self._calculate_streaks(workouts)
        
        return {
            "preferred_days": preferred_days,
            "rest_day": rest_day,
            "longest_streak": longest_streak,
            "longest_gap": longest_gap,
        }
    
    def _calculate_streaks(self, workouts: List[Dict]) -> Tuple[int, int]:
        """Calcula racha mas larga de entrenamientos y gap mas largo."""
        completed_dates = sorted(set(w["_date"] for w in workouts if self._is_completed(w)))
        
        if not completed_dates:
            return 0, 0
        
        # Streak mas largo
        max_streak = 1
        current_streak = 1
        
        for i in range(1, len(completed_dates)):
            diff = (completed_dates[i] - completed_dates[i-1]).days
            if diff == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        # Gap mas largo
        max_gap = 0
        for i in range(1, len(completed_dates)):
            gap = (completed_dates[i] - completed_dates[i-1]).days - 1
            max_gap = max(max_gap, gap)
        
        return max_streak, max_gap
    
    def _calculate_trends(self, workouts: List[Dict], today: date) -> Dict[str, str]:
        """
        Calcula tendencias comparando ultimas 4 semanas vs 4 anteriores.
        """
        mid_point = today - timedelta(days=28)
        
        recent = [w for w in workouts if w["_date"] > mid_point]
        older = [w for w in workouts if w["_date"] <= mid_point]
        
        def get_avg_tss(ws):
            completed = [w for w in ws if self._is_completed(w)]
            if not completed:
                return 0
            return sum(self._parse_tss(w) for w in completed) / len(completed)
        
        def get_avg_if(ws):
            completed = [w for w in ws if self._is_completed(w)]
            if not completed:
                return 0
            return sum(self._parse_intensity_factor(w) for w in completed) / len(completed)
        
        recent_tss = get_avg_tss(recent)
        older_tss = get_avg_tss(older)
        recent_if = get_avg_if(recent)
        older_if = get_avg_if(older)
        
        def trend(recent_val, older_val, threshold=0.1):
            if older_val == 0:
                return "stable"
            change = (recent_val - older_val) / older_val
            if change > threshold:
                return "increasing"
            elif change < -threshold:
                return "decreasing"
            return "stable"
        
        return {
            "volume": trend(recent_tss, older_tss),
            "intensity": trend(recent_if, older_if, 0.05),
        }
    
    def _calculate_type_distribution(self, workouts: List[Dict]) -> Dict[str, float]:
        """Calcula distribucion por tipo de workout."""
        completed = [w for w in workouts if self._is_completed(w)]
        
        if not completed:
            return {}
        
        type_counts = Counter(self._get_workout_type(w) for w in completed)
        total = len(completed)
        
        return {
            wtype: round(count / total, 2) 
            for wtype, count in type_counts.items()
        }
    
    # --- Helpers de parsing ---
    
    def _is_completed(self, w: Dict) -> bool:
        """Determina si un workout fue completado."""
        # Buscar en varios campos posibles
        status = (
            w.get("status", "") or 
            w.get("workout_completed", "") or
            w.get("completed", "")
        )
        if isinstance(status, bool):
            return status
        if isinstance(status, str):
            return status.lower() in ("completed", "completado", "done", "true", "1")
        # Si tiene duracion completada, esta completado
        return bool(w.get("duration_completed") or w.get("completed_duration"))
    
    def _is_skipped(self, w: Dict) -> bool:
        """Determina si un workout fue omitido."""
        status = w.get("status", "") or w.get("workout_completed", "")
        if isinstance(status, str):
            return status.lower() in ("skipped", "omitido", "missed")
        return False
    
    def _parse_duration_hours(self, w: Dict) -> float:
        """Parsea duracion a horas."""
        duration = (
            w.get("duration_completed") or 
            w.get("completed_duration") or
            w.get("duration") or
            w.get("planned_duration") or
            "0:00:00"
        )
        return self._duration_to_hours(duration)
    
    def _duration_to_hours(self, duration: Any) -> float:
        """Convierte string de duracion (h:mm:ss) a horas."""
        if not duration:
            return 0.0
        if isinstance(duration, (int, float)):
            return float(duration) / 60  # Asumimos minutos
        
        try:
            parts = str(duration).split(":")
            if len(parts) == 3:
                h, m, s = map(float, parts)
                return h + m/60 + s/3600
            elif len(parts) == 2:
                m, s = map(float, parts)
                return m/60 + s/3600
            return float(parts[0]) / 60
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_distance(self, w: Dict) -> float:
        """Parsea distancia en km."""
        distance = (
            w.get("distance_completed") or 
            w.get("completed_distance") or
            w.get("distance") or
            w.get("planned_distance") or
            0
        )
        try:
            return float(str(distance).replace("km", "").strip())
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_tss(self, w: Dict) -> int:
        """Parsea TSS."""
        tss = (
            w.get("tss_completed") or 
            w.get("completed_tss") or
            w.get("tss") or
            w.get("planned_tss") or
            0
        )
        try:
            return int(float(str(tss)))
        except (ValueError, TypeError):
            return 0
    
    def _parse_elevation(self, w: Dict) -> int:
        """Parsea elevacion en metros."""
        elev = w.get("elevation") or w.get("elevation_gain") or 0
        try:
            return int(float(str(elev)))
        except (ValueError, TypeError):
            return 0
    
    def _classify_intensity_robust(self, w: Dict) -> Tuple[str, float]:
        """
        Clasifica intensidad usando multiples senales.
        
        Orden de prioridad:
        1. IF completado (si existe y es valido)
        2. HR como % de HRmax estimado (si hay datos de HR)
        3. TSS/hora como proxy de intensidad
        4. Default conservador (Z2)
        
        Args:
            w: Workout dict (normalizado o raw)
            
        Returns:
            Tuple de (zona, confianza)
            zona: "easy" | "moderate" | "hard"
            confianza: 0.0 - 1.0
        """
        signals: List[Tuple[str, str, float]] = []  # (source, zone, weight)
        
        # 1. Intentar IF completado (mayor confianza)
        if_val = self._parse_intensity_factor_safe(w)
        if if_val is not None:
            if if_val < self.IF_EASY_THRESHOLD:
                signals.append(("if", "easy", 1.0))
            elif if_val < self.IF_MODERATE_THRESHOLD:
                signals.append(("if", "moderate", 1.0))
            else:
                signals.append(("if", "hard", 1.0))
        
        # 2. Intentar HR como % de HRmax
        hr_zone = self._classify_by_heart_rate(w)
        if hr_zone:
            signals.append(("hr", hr_zone, 0.8))
        
        # 3. Intentar TSS/hora como proxy
        tss_zone = self._classify_by_tss_rate(w)
        if tss_zone:
            signals.append(("tss_rate", tss_zone, 0.6))
        
        # Si no hay senales, usar default conservador
        if not signals:
            return ("easy", 0.1)  # Baja confianza
        
        # Calcular zona por consenso ponderado
        zone_scores = {"easy": 0.0, "moderate": 0.0, "hard": 0.0}
        total_weight = 0.0
        
        for source, zone, weight in signals:
            zone_scores[zone] += weight
            total_weight += weight
        
        # Zona con mayor score
        final_zone = max(zone_scores, key=zone_scores.get)
        
        # Confianza basada en peso total y consenso
        confidence = total_weight / 3.0  # Normalizado (max 3 senales)
        if len(signals) > 1:
            # Bonus por consenso
            top_score = zone_scores[final_zone]
            if top_score / total_weight > 0.7:
                confidence = min(confidence + 0.2, 1.0)
        
        return (final_zone, round(confidence, 2))
    
    def _parse_intensity_factor_safe(self, w: Dict) -> Optional[float]:
        """
        Parsea Intensity Factor de forma segura.
        
        Busca en campos normalizados y legacy, retorna None si no hay dato valido.
        """
        # Campos normalizados (prioridad)
        if_val = w.get("if_completed")
        
        # Campos legacy
        if if_val is None:
            if_val = w.get("if") or w.get("intensity_factor") or w.get("IF")
        
        if if_val is None:
            return None
        
        try:
            val = float(str(if_val))
            # Normalizar si viene como porcentaje
            if val > 2:
                val = val / 100
            # Validar rango
            if 0.4 <= val <= 1.5:
                return val
            return None
        except (ValueError, TypeError):
            return None
    
    def _classify_by_heart_rate(self, w: Dict) -> Optional[str]:
        """
        Clasifica intensidad basado en HR promedio.
        
        Usa 220-edad como HRmax estimado si no hay dato real.
        Umbrales: <70% easy, 70-85% moderate, >85% hard
        """
        hr_avg = w.get("hr_avg")
        if hr_avg is None:
            # Intentar campo legacy
            hr_avg = w.get("heart_rate_avg") or w.get("avg_hr")
        
        if not hr_avg:
            return None
        
        try:
            hr_avg = int(float(str(hr_avg)))
        except (ValueError, TypeError):
            return None
        
        if hr_avg < 40 or hr_avg > 220:
            return None
        
        # Usar HRmax del workout si existe, sino estimar
        hr_max = w.get("hr_max")
        if hr_max:
            try:
                hr_max = int(float(str(hr_max)))
            except (ValueError, TypeError):
                hr_max = None
        
        # HRmax estimado conservador (asumiendo atleta de 35-40 anos)
        if not hr_max or hr_max < hr_avg:
            hr_max = 185  # Estimado conservador
        
        hr_pct = hr_avg / hr_max
        
        if hr_pct < 0.70:
            return "easy"
        elif hr_pct < 0.85:
            return "moderate"
        else:
            return "hard"
    
    def _classify_by_tss_rate(self, w: Dict) -> Optional[str]:
        """
        Clasifica intensidad basado en TSS/hora.
        
        Umbrales aproximados:
        - <50 TSS/hora: easy
        - 50-70 TSS/hora: moderate
        - >70 TSS/hora: hard
        """
        tss = self._parse_tss(w)
        duration_hours = self._parse_duration_hours(w)
        
        if not tss or not duration_hours or duration_hours < 0.1:
            return None
        
        tss_per_hour = tss / duration_hours
        
        if tss_per_hour < 50:
            return "easy"
        elif tss_per_hour < 70:
            return "moderate"
        else:
            return "hard"
    
    def _parse_intensity_factor(self, w: Dict) -> float:
        """
        Parsea Intensity Factor (version legacy para compatibilidad).
        
        Usa _parse_intensity_factor_safe y retorna default si no hay dato.
        """
        if_val = self._parse_intensity_factor_safe(w)
        if if_val is not None:
            return if_val
        
        # Intentar clasificacion alternativa
        zone, _ = self._classify_intensity_robust(w)
        
        # Mapear zona a IF aproximado
        zone_to_if = {
            "easy": 0.65,
            "moderate": 0.82,
            "hard": 0.95
        }
        
        return zone_to_if.get(zone, 0.65)
    
    def _get_workout_type(self, w: Dict) -> str:
        """Obtiene tipo de workout."""
        wtype = w.get("workout_type") or w.get("type") or w.get("activity_type") or "Unknown"
        return str(wtype).title()
    
    def _empty_metrics(self, today: date, start: date, period_days: int) -> ComputedMetrics:
        """Retorna metricas vacias cuando no hay datos."""
        return ComputedMetrics(
            computed_at=datetime.utcnow(),
            period_days=period_days,
            period_start=start,
            period_end=today,
            total_workouts=0,
            total_completed=0,
            total_skipped=0,
            total_hours=0.0,
            total_distance_km=0.0,
            total_tss=0,
            total_elevation_m=0,
            avg_weekly_hours=0.0,
            avg_weekly_distance=0.0,
            avg_weekly_tss=0.0,
            avg_workouts_per_week=0.0,
            avg_workout_duration_min=0.0,
            ctl=0.0,
            atl=0.0,
            tsb=0.0,
            ramp_rate=0.0,
            adherence_rate=0.0,
            consistency_score=0.0,
            pct_easy=0.0,
            pct_moderate=0.0,
            pct_hard=0.0,
        )
