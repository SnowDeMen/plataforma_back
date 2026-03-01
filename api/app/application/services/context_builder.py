"""
Constructor de contexto optimizado para el LLM.

Genera prompts estructurados y compactos para la generacion de planes,
reduciendo el uso de tokens mientras mantiene la informacion relevante.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import date, timedelta

from app.domain.entities.training_metrics import ComputedMetrics
from app.domain.entities.alerts import TrainingAlert, AlertSeverity


class AthleteContextBuilder:
    """
    Constructor de contexto optimizado para el LLM.
    
    Genera prompts estructurados que reducen el uso de tokens de ~3000
    a ~800-1000 mientras mantienen la informacion relevante para
    la generacion de planes de entrenamiento.
    """
    
    # Mensajes de alerta por ID para inclusion en prompts
    ALERT_MESSAGES = {
        "high_ramp_rate": "ALERTA: Ramp rate alto - riesgo de sobreentrenamiento",
        "low_adherence": "ALERTA: Adherencia baja - revisar viabilidad del plan",
        "negative_tsb": "ALERTA: Fatiga acumulada alta - priorizar recuperacion",
        "low_polarization": "NOTA: Distribucion de intensidad no optima",
        "long_gap": "NOTA: Gaps largos detectados en historial",
    }
    
    def build_performance_context(
        self, 
        metrics: ComputedMetrics,
        recent_workouts: Optional[List[Dict]] = None,
        max_recent: int = 5
    ) -> str:
        """
        Genera contexto de performance optimizado para el LLM.
        
        Args:
            metrics: Metricas computadas del atleta
            recent_workouts: Lista de workouts recientes (opcional)
            max_recent: Maximo de workouts recientes a incluir
            
        Returns:
            String de contexto (~500 tokens)
        """
        lines = []
        
        # Seccion: Estado de carga
        lines.append("### Estado Actual de Entrenamiento")
        lines.append("")
        lines.append("**Carga de Entrenamiento (ultimos 90 dias):**")
        lines.append(
            f"- CTL (Fitness): {metrics.ctl:.0f} | "
            f"ATL (Fatiga): {metrics.atl:.0f} | "
            f"TSB (Forma): {metrics.tsb:.0f}"
        )
        
        # Ramp rate con alerta si es alto
        ramp_alert = " [RIESGO]" if metrics.ramp_rate > 5 else ""
        lines.append(f"- Ramp Rate: {metrics.ramp_rate:.1f}/semana{ramp_alert}")
        
        # Estado interpretado
        load_status = metrics.get_load_status()
        status_text = {
            "fresh": "Descansado, listo para intensidad",
            "neutral": "Balance normal",
            "fatigued": "Fatiga moderada, cuidar recuperacion",
            "overtrained": "Riesgo alto, priorizar descanso"
        }
        lines.append(f"- Estado: {status_text.get(load_status, 'N/A')}")
        
        # Seccion: Volumenes
        lines.append("")
        lines.append("**Volumenes Semanales Promedio:**")
        lines.append(
            f"- Horas: {metrics.avg_weekly_hours:.1f}h | "
            f"Distancia: {metrics.avg_weekly_distance:.0f}km | "
            f"TSS: {metrics.avg_weekly_tss:.0f}"
        )
        lines.append(f"- Entrenamientos/semana: {metrics.avg_workouts_per_week:.1f}")
        
        # Seccion: Adherencia
        lines.append("")
        lines.append("**Adherencia y Consistencia:**")
        adherence_warning = " [BAJO]" if metrics.adherence_rate < 0.7 else ""
        lines.append(
            f"- Tasa de completado: {metrics.adherence_rate:.0%}{adherence_warning} | "
            f"Consistencia: {metrics.consistency_score:.0%}"
        )
        
        # Seccion: Distribucion de intensidad
        lines.append("")
        lines.append("**Distribucion de Intensidad:**")
        polarization_note = ""
        if metrics.pct_easy < 0.7:
            polarization_note = " [Mejorar polarizacion]"
        lines.append(
            f"- Facil (Z1-Z2): {metrics.pct_easy:.0%} | "
            f"Moderado (Z3): {metrics.pct_moderate:.0%} | "
            f"Intenso (Z4-Z5): {metrics.pct_hard:.0%}{polarization_note}"
        )
        
        # Seccion: Tendencias
        lines.append("")
        lines.append("**Tendencias (4 semanas):**")
        lines.append(
            f"- Volumen: {metrics.volume_trend} | "
            f"Intensidad: {metrics.intensity_trend}"
        )
        
        # Seccion: Patrones
        if metrics.preferred_workout_days:
            lines.append("")
            lines.append("**Patrones:**")
            lines.append(f"- Dias preferidos: {', '.join(metrics.preferred_workout_days)}")
            if metrics.typical_rest_day:
                lines.append(f"- Descanso tipico: {metrics.typical_rest_day}")
        
        # Seccion: Alertas activas
        if metrics.active_alerts:
            lines.append("")
            lines.append("**Alertas Activas:**")
            for alert in metrics.active_alerts:
                severity_icon = "!" if alert.severity == AlertSeverity.CRITICAL else "-"
                lines.append(f"{severity_icon} {alert.title}: {alert.message}")
        
        # Seccion: Workouts recientes
        if recent_workouts:
            lines.append("")
            lines.append("**Ultimos Entrenamientos:**")
            for w in recent_workouts[:max_recent]:
                w_date = w.get("date", w.get("_date_str", "N/A"))
                w_type = w.get("type", w.get("workout_type", "N/A"))
                w_duration = w.get("duration", w.get("duration_completed", "N/A"))
                w_distance = w.get("distance", w.get("distance_completed", "N/A"))
                w_tss = w.get("tss", w.get("tss_completed", "N/A"))
                w_status = "OK" if w.get("completed", True) else "Omitido"
                
                # Esfuerzo percibido (solo si hay datos)
                rpe_parts: List[str] = []
                w_feel = w.get("feel")
                w_rpe = w.get("rpe")
                if w_feel is not None:
                    feel_lbl = w.get("feel_label", "")
                    rpe_parts.append(
                        f"Sensacion:{w_feel}/5" + (f"({feel_lbl})" if feel_lbl else "")
                    )
                if w_rpe is not None:
                    rpe_lbl = w.get("rpe_label", "")
                    rpe_parts.append(
                        f"RPE:{w_rpe}/10" + (f"({rpe_lbl})" if rpe_lbl else "")
                    )
                rpe_info = " | " + " ".join(rpe_parts) if rpe_parts else ""
                
                lines.append(
                    f"- {w_date} | {w_type} | {w_duration} | "
                    f"{w_distance}km | TSS:{w_tss} | {w_status}{rpe_info}"
                )
        
        return "\n".join(lines)
    
    def build_alerts_context(self, alerts: List[TrainingAlert]) -> str:
        """
        Genera seccion de alertas para el prompt.
        Solo incluye alertas de severidad WARNING o CRITICAL.
        
        Args:
            alerts: Lista de alertas activas
            
        Returns:
            String con alertas relevantes
        """
        relevant = [
            a for a in alerts 
            if a.severity in (AlertSeverity.WARNING, AlertSeverity.CRITICAL)
        ]
        
        if not relevant:
            return ""
        
        lines = ["### ALERTAS IMPORTANTES", ""]
        
        for alert in relevant:
            severity = "CRITICO" if alert.severity == AlertSeverity.CRITICAL else "ALERTA"
            lines.append(f"**{severity}: {alert.title}**")
            lines.append(f"- {alert.message}")
            lines.append(f"- Recomendacion: {alert.recommendation}")
            lines.append("")
        
        return "\n".join(lines)
    
    def build_full_context(
        self,
        athlete_data: Dict[str, Any],
        computed_metrics: Optional[Dict[str, Any]] = None,
        recent_workouts: Optional[List[Dict]] = None,
        start_date: Optional[date] = None
    ) -> str:
        """
        Construye el contexto completo para generacion de plan.
        
        Combina:
        - Datos basicos del atleta
        - Metricas computadas (si existen)
        - Alertas activas
        - Workouts recientes
        
        Args:
            athlete_data: Diccionario con datos del atleta
            computed_metrics: Metricas computadas (dict desde DB)
            recent_workouts: Lista de workouts recientes
            start_date: Fecha de inicio del plan
            
        Returns:
            String de contexto completo (~800-1000 tokens)
        """
        lines = []
        
        # Encabezado
        name = athlete_data.get('athlete_name', 'Atleta')
        lines.append(f"## ATLETA: {name}")
        lines.append("")
        
        # Datos basicos
        lines.append("### Datos Basicos")
        age = athlete_data.get('age', 'No especificado')
        lines.append(f"- Edad: {age} anos")
        
        personal = athlete_data.get('personal') or {}
        if personal.get('genero'):
            lines.append(f"- Genero: {personal['genero']}")
        
        lines.append(f"- Disciplina: {athlete_data.get('discipline', 'Running')}")
        lines.append(f"- Nivel: {athlete_data.get('level', 'Recreativo')}")
        lines.append(f"- Experiencia: {athlete_data.get('experience', 'No especificado')}")
        
        # Objetivo
        lines.append("")
        lines.append("### Objetivo")
        lines.append(f"- Meta principal: {athlete_data.get('goal', 'Mejorar condicion fisica')}")
        
        deportiva = athlete_data.get('deportiva') or {}
        if deportiva.get('eventoObjetivo'):
            lines.append(f"- Evento objetivo: {deportiva['eventoObjetivo']}")
        if deportiva.get('diasParaEvento'):
            lines.append(f"- Dias para el evento: {deportiva['diasParaEvento']}")
        
        # Disponibilidad
        lines.append("")
        lines.append("### Disponibilidad")
        sesiones = personal.get('sesionesSemanales', '3-4')
        horas = personal.get('horasSemanales', '4-6 horas')
        lines.append(f"- Sesiones por semana: {sesiones}")
        lines.append(f"- Horas disponibles: {horas}")
        if personal.get('horarioPreferido'):
            lines.append(f"- Horario preferido: {personal['horarioPreferido']}")
        if personal.get('diaDescanso'):
            lines.append(f"- Dia de descanso preferido: {personal['diaDescanso']}")
        
        # Salud (breve)
        medica = athlete_data.get('medica') or {}
        if medica.get('enfermedades') and medica['enfermedades'] != 'Ninguna':
            lines.append("")
            lines.append("### Salud")
            lines.append(f"- Condiciones: {medica['enfermedades']}")
        
        # Records (si existen)
        records = deportiva.get('records') or {}
        if any(records.values()):
            lines.append("")
            lines.append("### Records Personales")
            if records.get('dist5k'):
                lines.append(f"- 5K: {records['dist5k']}")
            if records.get('dist10k'):
                lines.append(f"- 10K: {records['dist10k']}")
            if records.get('dist21k'):
                lines.append(f"- 21K: {records['dist21k']}")
            if records.get('maraton'):
                lines.append(f"- Maraton: {records['maraton']}")
        
        # Metricas computadas (si existen)
        if computed_metrics:
            lines.append("")
            metrics = ComputedMetrics.from_dict(computed_metrics)
            lines.append(self.build_performance_context(metrics, recent_workouts))
            
            # Alertas importantes
            if metrics.active_alerts:
                alerts_text = self.build_alerts_context(metrics.active_alerts)
                if alerts_text:
                    lines.append("")
                    lines.append(alerts_text)
        elif recent_workouts:
            # Sin metricas pero con historial
            lines.append("")
            lines.append("### Ultimos Entrenamientos")
            for w in recent_workouts[:5]:
                w_date = w.get('fecha', w.get('date', 'N/A'))
                w_type = w.get('tipo', w.get('type', 'N/A'))
                w_status = w.get('estado', w.get('status', 'N/A'))
                lines.append(f"- {w_date} | {w_type} | {w_status}")
        
        # Fechas del plan
        if start_date:
            lines.append("")
            lines.append("### Plan a Generar")
            end_date = start_date + timedelta(weeks=4)
            lines.append(f"- Fecha de inicio: {start_date.strftime('%Y-%m-%d')}")
            lines.append(f"- Fecha de fin: {end_date.strftime('%Y-%m-%d')}")
            lines.append("- Duracion: 4 semanas (28 dias)")
        
        return "\n".join(lines)
    
    def extract_recent_workouts(
        self, 
        performance_data: Dict[str, Any], 
        max_count: int = 5
    ) -> List[Dict]:
        """
        Extrae workouts recientes del historial para incluir en contexto.
        
        Args:
            performance_data: Dict de performance del atleta
            max_count: Maximo de workouts a extraer
            
        Returns:
            Lista de workouts mas recientes
        """
        training_history = performance_data.get("training_history", {})
        days = training_history.get("days", {})
        
        if not days:
            # Intentar formato alternativo
            workouts = performance_data.get("workouts", [])
            return workouts[:max_count] if workouts else []
        
        # Aplanar y ordenar por fecha
        all_workouts = []
        for date_str, day_workouts in days.items():
            for w in day_workouts:
                w["_date_str"] = date_str
                all_workouts.append(w)
        
        # Ordenar por fecha descendente (mas reciente primero)
        all_workouts.sort(key=lambda w: w.get("_date_str", ""), reverse=True)
        
        return all_workouts[:max_count]
