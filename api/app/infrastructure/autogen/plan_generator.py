"""
PlanGenerator - Servicio para generar y modificar planes de entrenamiento de 4 semanas.
Usa el LLM con Chain of Thought (CoT) para generar planes estructurados con justificaciones.
"""
import asyncio
import json
from typing import Optional, Dict, Any, Callable, List, Literal
from datetime import datetime, date, timedelta

from openai import AsyncOpenAI
from loguru import logger

from app.core.config import settings


# Prompt especializado para generacion de planes con Chain of Thought (CoT)
PLAN_GENERATION_SYSTEM_PROMPT = """Eres un entrenador profesional especializado en RUNNING y TRIATLON.
Tu tarea es generar un plan de entrenamiento estructurado de 4 semanas (28 dias).

## METODOLOGIA: CHAIN OF THOUGHT (CoT)

ANTES de generar el plan, debes:
1. ANALIZAR al atleta: fortalezas, areas a trabajar, restricciones
2. DECIDIR el enfoque de periodizacion apropiado
3. JUSTIFICAR cada decision de entrenamiento

## REGLAS CRITICAS

1. GENERA EXACTAMENTE 28 WORKOUTS (uno por dia, 7 dias x 4 semanas)
2. Incluye dias de descanso apropiados (1-2 por semana segun el atleta)
3. Respeta las restricciones medicas y disponibilidad del atleta
4. Progresion logica de carga: semanas 1-3 incrementan, semana 4 descarga
5. El plan debe ser realista y alcanzable para el nivel del atleta
6. INCLUYE JUSTIFICACIONES en cada semana y cada workout

## FORMATO DE SALIDA (JSON OBLIGATORIO)

Responde UNICAMENTE con un JSON valido con esta estructura:

```json
{
    "summary": "Resumen general del plan en 2-3 oraciones",
    "athlete_analysis": {
        "strengths": ["Lista de fortalezas identificadas"],
        "areas_to_work": ["Areas que necesitan mejora"],
        "key_constraints": ["Restricciones importantes a considerar"],
        "periodization_approach": "Enfoque de periodizacion elegido y por que"
    },
    "total_tss": 450,
    "total_distance_km": 120,
    "total_duration_hours": 18,
    "weeks": [
        {
            "week": 1,
            "focus": "Base aerobica y adaptacion",
            "reasoning": "Explicacion detallada de por que esta semana tiene este enfoque, considerando el estado del atleta y la progresion del plan",
            "load_distribution": "Justificacion de como se distribuye la carga en esta semana",
            "total_tss": 100,
            "total_distance_km": 28,
            "workouts": [
                {
                    "day": 1,
                    "date": "2025-01-06",
                    "workout_type": "Run",
                    "title": "Rodaje suave Z2",
                    "description": "Construir base aerobica",
                    "justification": "Explicacion de por que este dia tiene este entrenamiento especifico, considerando el dia anterior, el siguiente, y el objetivo de la semana",
                    "pre_activity_comments": "Calentamiento 10 min\\nBloque principal: 30 min Z2\\nEnfriamiento 5 min",
                    "duration": "0:45:00",
                    "distance": "7",
                    "tss": 35,
                    "intensity_factor": 0.70,
                    "average_pace": "6:26",
                    "elevation_gain": 50,
                    "calories": 400
                }
            ]
        }
    ]
}
```

## CAMPOS DE JUSTIFICACION (OBLIGATORIOS)

**A nivel de plan:**
- athlete_analysis.strengths: Fortalezas del atleta identificadas del contexto
- athlete_analysis.areas_to_work: Areas donde el atleta necesita mejorar
- athlete_analysis.key_constraints: Restricciones (lesiones, tiempo, preferencias)
- athlete_analysis.periodization_approach: Tipo de periodizacion y por que

**A nivel de semana:**
- reasoning: Por que esta semana tiene este enfoque especifico
- load_distribution: Como y por que se distribuye la carga asi

**A nivel de workout:**
- justification: Por que este dia tiene este entrenamiento

## TIPOS DE WORKOUT DISPONIBLES

- Run: Carrera (el mas comun para corredores)
- Bike: Ciclismo
- Swim: Natacion
- Strength: Fuerza (para triatletas)
- Event: Evento de competencia (carreras, triatlon, maraton, etc.)
- Day off: Dia de descanso (obligatorio incluir 1-2 por semana)

## PARAMETROS POR TIPO

**Run:**
- duration: formato "h:mm:ss" (ej: "1:00:00")
- distance: km como string (ej: "10")
- tss: Training Stress Score (50-100 tipico)
- intensity_factor: 0.60-0.95 tipico
- average_pace: "mm:ss" por km (ej: "5:30")
- elevation_gain: metros
- calories: kcal estimadas

**Event:**
- title: Nombre del evento (ej: "Maraton CDMX", "Triatlon Sprint")
- description: Descripcion del evento
- duration: Duracion estimada
- distance: Distancia total
- tss: TSS estimado del evento
- Usar workout_type: "Event" para cualquier competencia o carrera objetivo

**Day off:**
- Solo incluir title: "Descanso", description: "Recuperacion"
- justification: Por que este dia es descanso
- No incluir duration, distance, etc.

## CONSIDERACIONES DE TSS

- Atleta recreativo: 200-350 TSS total
- Atleta competitivo: 350-500 TSS total
- Atleta elite: 500-700+ TSS total

RESPONDE SOLO CON EL JSON, SIN TEXTO ADICIONAL.
"""


# Prompt especializado para modificacion de planes con deteccion de riesgos
PLAN_MODIFICATION_SYSTEM_PROMPT = """Eres un entrenador profesional especializado en RUNNING y TRIATLON.
Tu tarea es MODIFICAR un plan de entrenamiento existente segun las instrucciones del usuario.

## CONTEXTO

Te proporcionare:
1. El analisis original del atleta (athlete_analysis)
2. El plan actual completo con todas sus justificaciones
3. El alcance de la modificacion (dia, semana, o plan completo)
4. Las instrucciones especificas del usuario
5. Si el usuario esta forzando un cambio previamente advertido

## REGLAS DE MODIFICACION

1. RESPETA la coherencia general del plan
2. Si modificas un dia, considera el impacto en los dias adyacentes
3. Si modificas una semana, ajusta la progresion de carga apropiadamente
4. ACTUALIZA las justificaciones de los elementos modificados
5. Mantiene el mismo formato JSON del plan original
6. NO cambies elementos que no necesiten cambio

## EVALUACION DE RIESGOS (CRITICO)

ANTES de aplicar cualquier cambio, EVALUA si la solicitud presenta riesgos:

### Riesgos que REQUIEREN CONFIRMACION:
- Competencias muy cercanas entre si (maratones, ultras, ironman < 14 dias entre si)
- Sesiones de alta intensidad en dias consecutivos
- Eliminar periodos de descarga o tapering antes de competencia
- Volumen o intensidad excesiva para el nivel del atleta
- Entrenamientos incompatibles con lesiones o condiciones medicas
- Saltar progresion de carga (aumento > 10% semanal)
- Entrenamientos inmediatamente post-competencia sin recuperacion

### Cuando detectes un riesgo:
1. NO apliques el cambio directamente
2. Retorna `requires_confirmation: true`
3. Explica el riesgo claramente en `risk_warning`
4. Proporciona una alternativa segura en `safe_alternative`

## FORMATO DE RESPUESTA

### Si NO hay riesgos (cambio seguro):

```json
{
    "requires_confirmation": false,
    "modification_summary": "Descripcion breve de los cambios realizados",
    "changes_made": [
        {
            "type": "day|week|plan",
            "target": "identificador del elemento modificado",
            "original": "resumen de lo que habia",
            "new": "resumen de lo que hay ahora",
            "reason": "por que se hizo este cambio"
        }
    ],
    "updated_plan": {
        // Plan completo actualizado
    }
}
```

### Si HAY riesgos (requiere confirmacion):

Solo devuelve la advertencia y la alternativa sugerida. NO incluyas planes actualizados en esta etapa.

```json
{
    "requires_confirmation": true,
    "risk_warning": "Explicacion clara del riesgo detectado y por que es peligroso",
    "risk_category": "categoria del riesgo (ej: 'recuperacion_insuficiente', 'sobrecarga', 'lesion_potencial')",
    "user_request_summary": "Resumen de lo que el usuario quiere hacer",
    "safe_alternative": {
        "description": "Descripcion de la alternativa segura propuesta",
        "workout_preview": {
            "title": "Titulo del workout alternativo",
            "workout_type": "Tipo",
            "duration": "Duracion si aplica",
            "tss": "TSS estimado"
        }
    }
}
```

### Si NO hay riesgos O el usuario está confirmando (force_apply=true/use_safe_alternative=true):

Aplica los cambios y devuelve SOLO la parte afectada según el `scope` para ahorrar tokens y tiempo:

- Si scope="day": Devuelve el objeto del workout modificado en `updated_workout`.
- Si scope="week": Devuelve el objeto de la semana modificada (incluyendo sus 7 workouts) en `updated_week`.
- Si scope="plan": Devuelve el plan completo actualizado en `updated_plan`.

```json
{
    "requires_confirmation": false,
    "modification_summary": "Descripcion breve de los cambios realizados",
    "changes_made": [
        {
            "type": "day|week|plan",
            "target": "identificador del elemento modificado",
            "original": "resumen de lo que habia",
            "new": "resumen de lo que hay ahora",
            "reason": "por que se hizo este cambio"
        }
    ],
    // Retorna SOLO UNO de estos tres segun el scope:
    "updated_workout": { ... }, 
    "updated_week": { ... },
    "updated_plan": { ... }
}
```

## IMPORTANTE

- Un experto usara este sistema, pero SIEMPRE advierte sobre riesgos
- El usuario tiene la ultima palabra, pero debe estar informado
- Si `force_apply: true` en el contexto: Ignora los riesgos y aplica la SOLICITUD ORIGINAL del usuario.
- Si `use_safe_alternative: true` en el contexto: Ignora la solicitud original riesgosa y aplica estrictamente la ALTERNATIVA SEGURA que propusiste.
- Mantén la coherencia del TSS total y la progresion de carga
- Las justificaciones de los elementos modificados deben reflejar el nuevo razonamiento

RESPONDE SOLO CON EL JSON, SIN TEXTO ADICIONAL.
"""


class PlanGenerator:
    """
    Generador y modificador de planes de entrenamiento usando LLM con CoT.
    
    Genera planes estructurados de 4 semanas con justificaciones a nivel
    de semana y workout. Permite modificaciones parciales manteniendo
    coherencia con el contexto original.
    """
    
    def __init__(self, model: Optional[str] = None):
        """
        Inicializa el generador de planes.
        
        Args:
            model: Modelo de LLM a usar (default: settings.AUTOGEN_MODEL)
        """
        self.model = model or getattr(settings, 'AUTOGEN_MODEL', 'gpt-4o')
        self._client: Optional[AsyncOpenAI] = None
    
    async def _ensure_client(self) -> None:
        """Inicializa el cliente de OpenAI si no existe."""
        if not self._client:
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    def _get_api_params(self, messages: List[Dict], max_tokens: int = 8000) -> Dict:
        """
        Construye los parametros de la API segun el modelo.
        
        Args:
            messages: Lista de mensajes para el chat
            max_tokens: Limite de tokens de respuesta
            
        Returns:
            Dict con parametros para la API
        """
        is_reasoning_model = (
            self.model.startswith("o1") or 
            self.model.startswith("gpt-5")
        )
        is_new_model = (
            self.model.startswith("gpt-4o") or
            self.model.startswith("gpt-5") or
            "gpt-4o" in self.model or
            "gpt-5" in self.model
        )
        
        api_params = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"}
        }
        
        if not is_reasoning_model:
            api_params["temperature"] = 0.7
        
        if is_reasoning_model:
            pass  # Sin limite para modelos de razonamiento
        elif is_new_model:
            api_params["max_completion_tokens"] = max_tokens
        else:
            api_params["max_tokens"] = max_tokens
        
        return api_params
    
    def _build_athlete_context_prompt(
        self, 
        athlete_context: Dict[str, Any],
        start_date: date
    ) -> str:
        """
        Construye el prompt con el contexto del atleta.
        
        Args:
            athlete_context: Datos del atleta
            start_date: Fecha de inicio del plan
            
        Returns:
            Prompt con contexto del atleta
        """
        # Extraer datos basicos
        name = athlete_context.get('athlete_name', 'Atleta')
        age = athlete_context.get('age', 'No especificado')
        discipline = athlete_context.get('discipline', 'Running')
        level = athlete_context.get('level', 'Recreativo')
        goal = athlete_context.get('goal', 'Mejorar condicion fisica')
        experience = athlete_context.get('experience', 'No especificado')
        
        # Datos personales
        personal = athlete_context.get('personal') or {}
        genero = personal.get('genero', 'No especificado')
        bmi = personal.get('bmi', 'No especificado')
        sesiones_semanales = personal.get('sesionesSemanales', '3-4')
        horas_semanales = personal.get('horasSemanales', '4-6 horas')
        horario_preferido = personal.get('horarioPreferido', 'Tarde')
        dia_descanso = personal.get('diaDescanso', 'Domingo')
        
        # Datos medicos
        medica = athlete_context.get('medica') or {}
        enfermedades = medica.get('enfermedades', 'Ninguna')
        horas_sueno = medica.get('horasSueno', 7)
        
        # Datos deportivos
        deportiva = athlete_context.get('deportiva') or {}
        evento_objetivo = deportiva.get('eventoObjetivo', goal)
        dias_para_evento = deportiva.get('diasParaEvento', 'No especificado')
        dedicacion = deportiva.get('dedicacion', sesiones_semanales)
        
        # Records
        records = deportiva.get('records') or {}
        records_str = ""
        if records:
            if records.get('dist5k'):
                records_str += f"- 5K: {records['dist5k']}\n"
            if records.get('dist10k'):
                records_str += f"- 10K: {records['dist10k']}\n"
            if records.get('dist21k'):
                records_str += f"- 21K: {records['dist21k']}\n"
            if records.get('maraton'):
                records_str += f"- Maraton: {records['maraton']}\n"
        
        # Historial de entrenamientos
        performance = athlete_context.get('performance') or {}
        workouts_history = performance.get('workouts', [])
        history_str = ""
        if workouts_history:
            history_str = "\n### Ultimos entrenamientos:\n"
            for w in workouts_history[:5]:
                estado = w.get('estado', '')
                tipo = w.get('tipo', '')
                fecha = w.get('fecha', '')
                dur_comp = w.get('duracionComp', w.get('duracionPlan', ''))
                dist_comp = w.get('distanciaComp', w.get('distanciaPlan', ''))
                tss = w.get('tssComp', w.get('tssPlan', ''))
                history_str += f"- {fecha} | {tipo} | {estado} | {dur_comp} | {dist_comp} | TSS: {tss}\n"
        
        # Calcular fechas
        end_date = start_date + timedelta(weeks=4)
        
        prompt = f"""## ATLETA: {name}

### Datos Basicos
- Edad: {age} anos
- Genero: {genero}
- BMI: {bmi}
- Disciplina: {discipline}
- Nivel: {level}
- Experiencia: {experience}

### Objetivo
- Meta principal: {goal}
- Evento objetivo: {evento_objetivo}
- Dias para el evento: {dias_para_evento}

### Disponibilidad
- Sesiones por semana: {sesiones_semanales}
- Horas disponibles: {horas_semanales}
- Horario preferido: {horario_preferido}
- Dia de descanso preferido: {dia_descanso}
- Dedicacion: {dedicacion}

### Salud
- Condiciones medicas: {enfermedades}
- Horas de sueno: {horas_sueno}

### Records Personales
{records_str if records_str else "No disponibles"}

{history_str}

## PLAN A GENERAR

- Fecha de inicio: {start_date.strftime('%Y-%m-%d')} ({start_date.strftime('%A')})
- Fecha de fin: {end_date.strftime('%Y-%m-%d')}
- Duracion: 4 semanas (28 dias)

## INSTRUCCIONES

1. Primero, ANALIZA al atleta e incluye tu analisis en "athlete_analysis"
2. Luego, genera el plan con JUSTIFICACIONES en cada semana y cada workout
3. Asegurate de que las justificaciones expliquen el "por que" de cada decision

Genera un plan de 4 semanas apropiado para este atleta.
Incluye las fechas reales para cada workout comenzando desde {start_date.strftime('%Y-%m-%d')}.
"""
        
        return prompt
    
    async def generate(
        self,
        athlete_context: Dict[str, Any],
        start_date: Optional[date] = None,
        on_progress: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Genera un plan de entrenamiento de 4 semanas con justificaciones CoT.
        
        Args:
            athlete_context: Contexto completo del atleta
            start_date: Fecha de inicio (default: proximo lunes)
            on_progress: Callback para reportar progreso (progress%, message)
            
        Returns:
            Dict con el plan estructurado incluyendo justificaciones
        """
        await self._ensure_client()
        
        # Calcular fecha de inicio si no se proporciona
        if not start_date:
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            start_date = today + timedelta(days=days_until_monday)
        
        if on_progress:
            on_progress(0, "Preparando contexto del atleta...")
        
        logger.info(f"Generando plan con CoT para: {athlete_context.get('athlete_name', 'Unknown')}")
        
        # Construir prompt
        athlete_prompt = self._build_athlete_context_prompt(athlete_context, start_date)
        
        if on_progress:
            on_progress(10, "Analizando perfil del atleta...")
        
        messages = [
            {"role": "system", "content": PLAN_GENERATION_SYSTEM_PROMPT},
            {"role": "user", "content": athlete_prompt}
        ]
        
        if on_progress:
            on_progress(20, "Generando plan con justificaciones...")
        
        try:
            api_params = self._get_api_params(messages, max_tokens=10000)
            response = await self._client.chat.completions.create(**api_params)
            
            if on_progress:
                on_progress(80, "Procesando respuesta...")
            
            content = response.choices[0].message.content
            
            if not content:
                raise ValueError("Respuesta vacia del LLM")
            
            plan_data = json.loads(content)
            
            # Validar estructura basica
            if 'weeks' not in plan_data:
                raise ValueError("Plan sin estructura de semanas")
            
            # Validar que tenga justificaciones
            has_analysis = 'athlete_analysis' in plan_data
            has_week_reasoning = all(
                'reasoning' in week 
                for week in plan_data.get('weeks', [])
            )
            
            if not has_analysis:
                logger.warning("Plan generado sin athlete_analysis")
            if not has_week_reasoning:
                logger.warning("Plan generado sin reasoning en semanas")
            
            # Limpiar datos numericos de todos los workouts generados
            for week in plan_data.get('weeks', []):
                for workout in week.get('workouts', []):
                    self._clean_workout_data(workout)
            
            # Contar workouts
            total_workouts = sum(
                len(week.get('workouts', []))
                for week in plan_data.get('weeks', [])
            )
            
            if on_progress:
                on_progress(90, f"Plan generado: {total_workouts} workouts")
            
            logger.info(
                f"Plan CoT generado: {total_workouts} workouts, "
                f"TSS total: {plan_data.get('total_tss', 'N/A')}, "
                f"Con analisis: {has_analysis}, Con reasoning: {has_week_reasoning}"
            )
            
            # Agregar metadata
            plan_data['generated_at'] = datetime.utcnow().isoformat()
            plan_data['start_date'] = start_date.isoformat()
            plan_data['end_date'] = (start_date + timedelta(weeks=4)).isoformat()
            plan_data['model_used'] = self.model
            plan_data['athlete_context'] = athlete_context  # Guardar contexto original
            
            if on_progress:
                on_progress(100, "Plan completado")
            
            return plan_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON del plan: {e}")
            raise ValueError(f"Error parseando respuesta del LLM: {e}")
        except Exception as e:
            logger.error(f"Error generando plan: {e}")
            raise
    
    async def modify_plan(
        self,
        current_plan: Dict[str, Any],
        scope: Literal['day', 'week', 'plan'],
        target: Optional[Dict[str, Any]],
        user_prompt: str,
        force_apply: bool = False,
        use_safe_alternative: bool = False,
        on_progress: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Modifica un plan existente segun las instrucciones del usuario.
        
        Incluye deteccion de riesgos: si el cambio es potencialmente peligroso,
        retorna una advertencia con alternativa segura y requiere confirmacion.
        
        Args:
            current_plan: Plan actual completo (con justificaciones)
            scope: Alcance de la modificacion ('day', 'week', 'plan')
            target: Detalles del elemento a modificar (workout o semana)
            user_prompt: Instrucciones del usuario para la modificacion
            force_apply: Si True, aplica el cambio aunque sea riesgoso
            use_safe_alternative: Si True, aplica la alternativa segura propuesta
            on_progress: Callback para reportar progreso
            
        Returns:
            Dict con:
            - requires_confirmation: bool - si necesita confirmacion
            - Si requires_confirmation=True:
              - risk_warning: str - advertencia de riesgo
              - safe_alternative: dict - alternativa segura
            - Si requires_confirmation=False:
              - plan: dict - plan actualizado
              - summary: str - resumen de cambios
              - changes: list - cambios realizados
        """
        await self._ensure_client()
        
        if on_progress:
            on_progress(0, "Preparando contexto de modificacion...")
        
        logger.info(
            f"Modificando plan - scope: {scope}, prompt: {user_prompt[:50]}..., "
            f"force: {force_apply}, safe_alt: {use_safe_alternative}"
        )
        
        # Extraer contexto del atleta del plan
        athlete_context = current_plan.get('athlete_context', {})
        
        # Construir contexto de modificacion
        start_ctx = datetime.utcnow()
        # Envolver en to_thread si el plan es muy grande para no bloquear al serializar
        modification_context = await asyncio.to_thread(
            self._build_modification_context,
            current_plan, scope, target, user_prompt, force_apply, use_safe_alternative
        )
        elapsed_ctx = (datetime.utcnow() - start_ctx).total_seconds()
        logger.info(f"[PLAN_MODIFY] Contexto construido en {elapsed_ctx:.4f}s")
        
        if on_progress:
            on_progress(20, "Evaluando riesgos y analizando cambios...")
        
        messages = [
            {"role": "system", "content": PLAN_MODIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": modification_context}
        ]
        
        prompt_len = sum(len(m["content"]) for m in messages)
        logger.info(f"[PLAN_MODIFY] Enviando peticion a OpenAI model={self.model}, prompt_chars={prompt_len}")
        
        start_time = datetime.utcnow()
        if on_progress:
            on_progress(40, "Generando modificaciones...")
        
        try:
            api_params = self._get_api_params(messages, max_tokens=16000)
            response = await self._client.chat.completions.create(**api_params)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"[PLAN_MODIFY] Respuesta recibida de OpenAI en {elapsed:.2f}s")
            
            if on_progress:
                on_progress(80, "Procesando cambios...")
            
            content = response.choices[0].message.content
            
            if not content:
                raise ValueError("Respuesta vacia del LLM")
            
            logger.debug("[PLAN_MODIFY] Parseando JSON de respuesta...")
            result = await asyncio.to_thread(json.loads, content)
            logger.debug("[PLAN_MODIFY] JSON parseado correctamente")
            
            # Limpiar datos de workouts para evitar errores de validacion (e.g. "10 por dia")
            if 'updated_workout' in result:
                result['updated_workout'] = self._clean_workout_data(result['updated_workout'])
            if 'updated_week' in result:
                for w in result['updated_week'].get('workouts', []):
                    self._clean_workout_data(w)
            if 'updated_plan' in result:
                 for week in result['updated_plan'].get('weeks', []):
                     for w in week.get('workouts', []):
                         self._clean_workout_data(w)
            
            # Limpiar alternativa segura si existe
            if 'safe_alternative' in result and 'workout_preview' in result['safe_alternative']:
                self._clean_workout_data(result['safe_alternative']['workout_preview'])

            # Limpiar historial de cambios (original/new) para que siempre sean strings
            if 'changes_made' in result:
                for c in result['changes_made']:
                    if 'original' in c and not isinstance(c['original'], str):
                        c['original'] = json.dumps(c['original'], ensure_ascii=False)
                    if 'new' in c and not isinstance(c['new'], str):
                        c['new'] = json.dumps(c['new'], ensure_ascii=False)

            # Verificar si requiere confirmacion
            requires_confirmation = result.get('requires_confirmation', False)
            
            # Determinar el tipo de decision
            if requires_confirmation and not force_apply and not use_safe_alternative:
                decision = 'warning'
            elif use_safe_alternative:
                decision = 'alternative'
            elif force_apply:
                decision = 'forced'
            else:
                decision = 'direct'
            
            # Combinar cambios parciales si existen (o clonar el actual si es solo advertencia)
            if decision == 'warning':
                # Solo clonamos para añadir el historial
                updated_plan = json.loads(json.dumps(current_plan))
            else:
                updated_plan = await self._merge_partial_updates(current_plan, result, scope, target)
            
            # Preservar metadata original
            updated_plan['generated_at'] = current_plan.get('generated_at')
            updated_plan['start_date'] = current_plan.get('start_date')
            updated_plan['end_date'] = current_plan.get('end_date')
            updated_plan['model_used'] = self.model
            updated_plan['athlete_context'] = athlete_context
            updated_plan['last_modified_at'] = datetime.utcnow().isoformat()
            
            # Construir la entrada del historial
            modification_history = current_plan.get('modification_history', [])
            history_entry = {
                'id': len(modification_history) + 1,
                'timestamp': datetime.utcnow().isoformat(),
                'scope': scope,
                'target': target,
                'user_prompt': user_prompt,
                'summary': result.get('modification_summary', f"Advertencia de riesgo detectada para: {user_prompt[:30]}..."),
                'changes': result.get('changes_made', []),
                'decision': decision,
                'had_risk_warning': requires_confirmation,
                'risk_warning': result.get('risk_warning') if requires_confirmation else None,
                'forced_by_user': force_apply,
                'used_safe_alternative': use_safe_alternative,
                'safe_alternative': result.get('safe_alternative') if requires_confirmation else None
            }
            modification_history.append(history_entry)
            updated_plan['modification_history'] = modification_history

            # AHORA SI: Retornar segun el tipo de decision
            if decision == 'warning':
                logger.warning(f"Modificacion requiere confirmacion: {result.get('risk_warning', '')}")
                if on_progress:
                    on_progress(100, "Advertencia de riesgo detectada")
                
                return {
                    'requires_confirmation': True,
                    'risk_warning': result.get('risk_warning', 'Cambio potencialmente riesgoso'),
                    'risk_category': result.get('risk_category', 'unknown'),
                    'user_request_summary': result.get('user_request_summary', user_prompt),
                    'safe_alternative': result.get('safe_alternative', {}),
                    'plan': updated_plan, # Ahora SI lleva el historial para el siguiente paso
                    'summary': f"Advertencia de riesgo: {result.get('risk_warning')[:100]}...",
                    'changes': []
                }
            
            apply_result = result
            
            return {
                'requires_confirmation': False,
                'plan': updated_plan,
                'summary': apply_result.get('modification_summary', ''),
                'changes': apply_result.get('changes_made', []),
                'decision': decision,
                'had_risk_warning': requires_confirmation
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON de modificacion: {e}")
            raise ValueError(f"Error parseando respuesta del LLM: {e}")
        except Exception as e:
            logger.error(f"Error modificando plan: {e}")
            raise

    def _clean_numeric(self, value: Any) -> Optional[int]:
        """Extracts only the numeric part of a string (e.g., '10 por día' -> 10)."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if not isinstance(value, str):
            return None
        
        # Remove non-numeric characters except for the first sequence of digits
        import re
        match = re.search(r'\d+', value)
        if match:
            return int(match.group())
        return None

    def _clean_workout_data(self, workout: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures numeric fields in a workout are actual numbers."""
        if not workout:
            return workout
            
        # Clean TSS
        if 'tss' in workout:
            workout['tss'] = self._clean_numeric(workout['tss'])
            
        # Clean Elevation Gain
        if 'elevation_gain' in workout:
            workout['elevation_gain'] = self._clean_numeric(workout['elevation_gain'])
            
        # Clean Calories
        if 'calories' in workout:
            workout['calories'] = self._clean_numeric(workout['calories'])
            
        # Intensity Factor (float)
        if 'intensity_factor' in workout:
            if isinstance(workout['intensity_factor'], str):
                import re
                match = re.search(r'\d+\.?\d*', workout['intensity_factor'])
                if match:
                    workout['intensity_factor'] = float(match.group())
                else:
                    workout['intensity_factor'] = None
        
        return workout

    async def _merge_partial_updates(
        self, 
        current_plan: Dict[str, Any], 
        result: Dict[str, Any], 
        scope: str, 
        target: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Integra cambios parciales (workout o semana) en el plan completo.
        Recalcula totales para mantener coherencia.
        """
        # Clonar el plan original para no mutar el input si algo falla
        new_plan = json.loads(json.dumps(current_plan))
        
        # Caso A: Retornó el plan completo (comportamiento original o scope="plan")
        if "updated_plan" in result and result["updated_plan"]:
            return result["updated_plan"]
            
        # Caso B: Retornó solo un día
        if scope == "day" and "updated_workout" in result:
            w_num = target.get("week")
            d_num = target.get("day")
            new_workout = result["updated_workout"]
            
            found = False
            for week in new_plan.get("weeks", []):
                if week.get("week") == w_num:
                    for i, workout in enumerate(week.get("workouts", [])):
                        if workout.get("day") == d_num:
                            week["workouts"][i] = new_workout
                            found = True
                            break
                    break
            if not found:
                logger.warning(f"No se pudo encontrar el workout para mezclar: semana {w_num}, dia {d_num}")

        # Caso C: Retornó solo una semana
        elif scope == "week" and "updated_week" in result:
            w_num = target.get("week")
            new_week = result["updated_week"]
            
            found = False
            for i, week in enumerate(new_plan.get("weeks", [])):
                if week.get("week") == w_num:
                    new_plan["weeks"][i] = new_week
                    found = True
                    break
            if not found:
                logger.warning(f"No se pudo encontrar la semana {w_num} para mezclar")

        # Recalcular totales de cada semana y del plan
        for week in new_plan.get("weeks", []):
            week_totals = self.calculate_totals({"weeks": [week]})
            week["total_tss"] = week_totals["total_tss"]
            week["total_distance_km"] = week_totals["total_distance_km"]
            # Convertir horas decimales a formato h:mm:ss para la semana
            h = int(week_totals["total_duration_hours"])
            m = int((week_totals["total_duration_hours"] * 60) % 60)
            week["total_duration"] = f"{h}:{m:02d}:00"
            
        plan_totals = self.calculate_totals(new_plan)
        new_plan["total_tss"] = plan_totals["total_tss"]
        new_plan["total_distance_km"] = plan_totals["total_distance_km"]
        new_plan["total_duration_hours"] = plan_totals["total_duration_hours"]
        
        return new_plan
    
    def _build_modification_context(
        self,
        current_plan: Dict[str, Any],
        scope: Literal['day', 'week', 'plan'],
        target: Optional[Dict[str, Any]],
        user_prompt: str,
        force_apply: bool = False,
        use_safe_alternative: bool = False
    ) -> str:
        """
        Construye el contexto para la modificacion del plan.
        
        Args:
            current_plan: Plan actual
            scope: Alcance de la modificacion
            target: Elemento objetivo
            user_prompt: Instrucciones del usuario
            force_apply: Si el usuario esta forzando un cambio riesgoso
            
        Returns:
            Prompt con todo el contexto necesario
        """
        # Analisis del atleta
        athlete_analysis = current_plan.get('athlete_analysis', {})
        athlete_context = current_plan.get('athlete_context', {})
        
        context_parts = []
        
        # Seccion 1: Contexto del atleta
        context_parts.append("## CONTEXTO DEL ATLETA\n")
        if athlete_context:
            context_parts.append(f"- Nombre: {athlete_context.get('athlete_name', 'No especificado')}")
            context_parts.append(f"- Nivel: {athlete_context.get('level', 'No especificado')}")
            context_parts.append(f"- Objetivo: {athlete_context.get('goal', 'No especificado')}")
        
        if athlete_analysis:
            context_parts.append("\n### Analisis Original:")
            context_parts.append(f"- Fortalezas: {', '.join(athlete_analysis.get('strengths', []))}")
            context_parts.append(f"- Areas a trabajar: {', '.join(athlete_analysis.get('areas_to_work', []))}")
            context_parts.append(f"- Restricciones: {', '.join(athlete_analysis.get('key_constraints', []))}")
            context_parts.append(f"- Periodizacion: {athlete_analysis.get('periodization_approach', 'No especificado')}")
        
        # Seccion 2: Alcance de la modificacion
        context_parts.append(f"\n## ALCANCE DE LA MODIFICACION: {scope.upper()}\n")
        
        if scope == 'day' and target:
            week_num = target.get('week', 0)
            day_num = target.get('day', 0)
            
            # Encontrar el workout especifico
            for week in current_plan.get('weeks', []):
                if week.get('week') == week_num:
                    context_parts.append(f"### Semana {week_num}")
                    context_parts.append(f"- Enfoque: {week.get('focus', '')}")
                    context_parts.append(f"- Razonamiento: {week.get('reasoning', '')}")
                    
                    for workout in week.get('workouts', []):
                        if workout.get('day') == day_num:
                            context_parts.append(f"\n### Workout a modificar (Dia {day_num}):")
                            context_parts.append(f"- Fecha: {workout.get('date', '')}")
                            context_parts.append(f"- Tipo: {workout.get('workout_type', '')}")
                            context_parts.append(f"- Titulo: {workout.get('title', '')}")
                            context_parts.append(f"- Justificacion original: {workout.get('justification', '')}")
                            context_parts.append(f"- Duracion: {workout.get('duration', '')}")
                            context_parts.append(f"- Distancia: {workout.get('distance', '')} km")
                            context_parts.append(f"- TSS: {workout.get('tss', '')}")
                            break
                    break
        
        elif scope == 'week' and target:
            week_num = target.get('week', 0)
            
            for week in current_plan.get('weeks', []):
                if week.get('week') == week_num:
                    context_parts.append(f"### Semana {week_num} a modificar:")
                    context_parts.append(f"- Enfoque: {week.get('focus', '')}")
                    context_parts.append(f"- Razonamiento: {week.get('reasoning', '')}")
                    context_parts.append(f"- Distribucion de carga: {week.get('load_distribution', '')}")
                    context_parts.append(f"- TSS total: {week.get('total_tss', '')}")
                    context_parts.append(f"\nWorkouts actuales:")
                    for w in week.get('workouts', []):
                        context_parts.append(
                            f"  - Dia {w.get('day')}: {w.get('title', '')} "
                            f"({w.get('workout_type', '')})"
                        )
                    break
        
        # Seccion 3: Plan completo actual
        context_parts.append("\n## PLAN ACTUAL COMPLETO\n")
        context_parts.append("```json")
        
        # Crear version limpia del plan para el contexto
        plan_for_context = {
            'summary': current_plan.get('summary', ''),
            'athlete_analysis': athlete_analysis,
            'total_tss': current_plan.get('total_tss', 0),
            'weeks': current_plan.get('weeks', [])
        }
        context_parts.append(json.dumps(plan_for_context, indent=2, ensure_ascii=False))
        context_parts.append("```")

        # Seccion NUEVA: Historial de modificaciones (Memoria)
        history = current_plan.get('modification_history', [])
        if history:
            context_parts.append("\n## HISTORIAL RECIENTE DE MODIFICACIONES (MEMORIA)\n")
            context_parts.append("Usa esto para entender el contexto de la conversacion actual:")
            for entry in history[-5:]:  # Mostrar ultimas 5
                role = "USUARIO"
                msg = entry.get('user_prompt', '')
                context_parts.append(f"- [{entry.get('timestamp', '')[:16]}] {role}: {msg}")
                context_parts.append(f"  ENTRENADOR: {entry.get('summary', '')}")
                
                if entry.get('had_risk_warning') and entry.get('safe_alternative'):
                    context_parts.append(f"  ADVERTENCIA: {entry.get('risk_warning')}")
                    context_parts.append(f"  ALTERNATIVA SEGURA PROPUESTA: {json.dumps(entry.get('safe_alternative'), ensure_ascii=False)}")
                
                if entry.get('used_safe_alternative'):
                    context_parts.append(f"  (Resultado: El usuario aceptó la alternativa segura)")
        
        # Seccion 4: Instrucciones del usuario
        context_parts.append(f"\n## INSTRUCCION DEL USUARIO\n")
        if use_safe_alternative:
            context_parts.append(f"INSTRUCCION REEMPlAZADA: El usuario originalmente pidió '{user_prompt}', ")
            context_parts.append("pero ahora ha RECHAZADO esa idea y te pide aplicar la ALTERNATIVA SEGURA que propusiste anteriormente.")
            context_parts.append("DEBES APLICAR LA ALTERNATIVA SEGURA. Busca los detalles de esta alternativa en el HISTORIAL DE MODIFICACIONES arriba.")
            context_parts.append("Los datos del workout o semana a aplicar están en el campo 'safe_alternative' del historial reciente.")
        else:
            context_parts.append(f'"{user_prompt}"')
        
        # Seccion 5: Estado de confirmacion
        if force_apply:
            context_parts.append("\n## CONFIRMACION DEL USUARIO: FORZAR CAMBIO\n")
            context_parts.append("**force_apply: true**")
            context_parts.append("El usuario ha confirmado que quiere aplicar SU cambio original")
            context_parts.append("a pesar de los riesgos. Procede a aplicar la solicitud original.")
        elif use_safe_alternative:
            context_parts.append("\n## CONFIRMACION DEL USUARIO: ACEPTAR ALTERNATIVA SEGURA\n")
            context_parts.append("**use_safe_alternative: true**")
            context_parts.append("El usuario ha aceptado la alternativa segura que propusiste anteriormente.")
            context_parts.append("Procede a aplicar la alternativa segura al plan.")
        else:
            context_parts.append("\n## EVALUACION DE RIESGO REQUERIDA\n")
            context_parts.append("Evalua si la solicitud presenta riesgos antes de aplicar.")
            context_parts.append("Si detectas riesgos, retorna requires_confirmation: true y describe la alternativa.")
        
        # Seccion 6: Recordatorio
        context_parts.append("\n## RECORDATORIO\n")
        context_parts.append("1. Modifica SOLO lo necesario para cumplir la solicitud")
        context_parts.append("2. Mantén la coherencia con el resto del plan")
        context_parts.append("3. Actualiza las justificaciones de los elementos modificados")
        context_parts.append("4. Considera el impacto en los dias/semanas adyacentes")
        context_parts.append("5. Respeta las restricciones del atleta")
        context_parts.append("6. SIEMPRE evalua riesgos primero (a menos que force_apply=true)")
        
        return "\n".join(context_parts)
    
    def extract_workouts_flat(self, plan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extrae todos los workouts del plan en una lista plana.
        
        Args:
            plan_data: Datos del plan con estructura de semanas
            
        Returns:
            Lista de workouts individuales
        """
        workouts = []
        
        for week in plan_data.get('weeks', []):
            week_num = week.get('week', 0)
            for workout in week.get('workouts', []):
                workout['week'] = week_num
                workouts.append(workout)
        
        return workouts
    
    def calculate_totals(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula totales del plan.
        
        Args:
            plan_data: Datos del plan
            
        Returns:
            Dict con totales calculados
        """
        total_tss = 0
        total_distance = 0
        total_duration_minutes = 0
        workout_count = 0
        rest_days = 0
        
        for week in plan_data.get('weeks', []):
            for workout in week.get('workouts', []):
                workout_count += 1
                
                if workout.get('workout_type', '').lower() == 'day off':
                    rest_days += 1
                    continue
                
                # TSS
                tss = workout.get('tss', 0)
                if tss:
                    total_tss += int(tss)
                
                # Distancia
                distance = workout.get('distance', '0')
                if distance:
                    try:
                        total_distance += float(distance)
                    except ValueError:
                        pass
                
                # Duracion
                duration = workout.get('duration', '')
                if duration:
                    parts = duration.split(':')
                    if len(parts) == 3:
                        h, m, s = map(int, parts)
                        total_duration_minutes += h * 60 + m + s / 60
        
        return {
            'total_tss': total_tss,
            'total_distance_km': round(total_distance, 1),
            'total_duration_hours': round(total_duration_minutes / 60, 1),
            'workout_count': workout_count,
            'rest_days': rest_days,
            'training_days': workout_count - rest_days
        }
