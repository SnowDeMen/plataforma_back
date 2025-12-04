"""
ChatAgent - Agente de chat con memoria persistente y function calling.
Soporta herramientas del MCP para interactuar con TrainingPeaks.
"""
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from openai import AsyncOpenAI
from autogen_core import MessageContext
from loguru import logger

from app.core.config import settings
from app.shared.utils.audit_logger import AuditLogger
from app.infrastructure.mcp.mcp_tools import MCPToolsAdapter
from .base_agent import BaseAgent, TextMessage, AgentResponse


class ChatMessage:
    """
    Representa un mensaje individual en el historial de chat.
    Estructura serializable para persistencia en base de datos.
    """
    
    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None
    ):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        self.metadata = metadata or {}
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el mensaje a diccionario para serializacion."""
        data = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """Crea un ChatMessage desde un diccionario."""
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id")
        )
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Formato compatible con la API de OpenAI."""
        msg = {
            "role": self.role,
            "content": self.content
        }
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        return msg


class ChatAgent(BaseAgent):
    """
    Agente de chat con memoria persistente y soporte para function calling.
    
    Caracteristicas:
    - Mantiene historial de conversacion en memoria y base de datos
    - System message configurable para personalizar comportamiento
    - Soporta restauracion de conversaciones previas
    - Integrado con herramientas del MCP para TrainingPeaks
    - Function calling automatico para ejecutar acciones
    
    Ejemplo de uso:
        agent = ChatAgent(
            name="asistente_entrenamiento",
            session_id="uuid-123",
            system_message="Eres un asistente de entrenamientos deportivos."
        )
        
        # Procesar mensaje (puede ejecutar herramientas automaticamente)
        response = await agent.process_message("Dame los entrenamientos de hoy")
    """
    
    # Mensaje de sistema por defecto - Especialista en entrenamientos
    DEFAULT_SYSTEM_MESSAGE = """Eres un entrenador especializado en RUNNING y TRIATLON con experiencia en la creacion de entrenamientos estructurados.

## TU ROL
Creas entrenamientos profesionales directamente en TrainingPeaks.
Trabajas con el atleta actualmente seleccionado en la sesion.
Tu objetivo es crear workouts COMPLETAMENTE RELLENOS con todos los campos disponibles.

## ESTRUCTURA DE CAMPOS AL CREAR WORKOUT

La herramienta crear_workout tiene CUATRO CAMPOS INDEPENDIENTES que DEBE completar TODOS:

### 1. FIELD: title (Titulo del Workout)
- Debe ser conciso y descriptivo
- Ejemplos: "Intervalos 5x1000m", "Rodaje + Técnica", "Tempo 20 min"

### 2. FIELD: description (Descripcion General)
- Explica el OBJETIVO general del entrenamiento
- Una o dos oraciones maximas
- Ejemplos: "Trabajo de VO2max con recuperaciones activas", "Construir base aeróbica"

### 3. FIELD: pre_activity_comments (Instrucciones para el Atleta)
- AQUI VA LA ESTRUCTURA DETALLADA con todos los pasos
- El atleta VEERA esto ANTES de empezar el entrenamiento
- Incluye: calentamiento, serie principal, enfriamiento, notas sobre intensidad, terreno, etc.
- Puedes usar saltos de linea y formato legible

### 4. FIELD: planned_values (Valores Planeados - MUY IMPORTANTE)
- ES UN DICCIONARIO con los parametros cuantitativos
- ESTOS VALORES RELLENAN LOS CAMPOS NUMERICOS EN TRAININGPEAKS
- Sin esto, TrainingPeaks no recibe los datos de duracion, distancia, etc.

### Parametros disponibles por tipo de Workout:

**Run (Carrera)** - Los mas comunes:
- "Duration": Duracion total en formato h:m:s. OBLIGATORIO. Ej: "1:30:00"
- "Distance": Distancia en km. RECOMENDADO. Ej: "12"
- "Average Pace": Ritmo promedio en min/km. Ej: "5:30"
- "TSS": Training Stress Score (100 = 1h a umbral). RECOMENDADO. Ej: "75"
- "IF": Intensity Factor (1.0 = umbral). Ej: "0.85"
- "Elevation Gain": Desnivel en metros. Ej: "150"
- "Calories": Kcal estimadas. Ej: "600" NOTA: ESTA NO ES OBLIGATORIA, SOLO ES PARA REFERENCIA
- "Work": kJ. Ej: "800"

**Bike (Ciclismo)** - Parámetros similares a Run:
- Duration, Distance, Average Speed (kph), TSS, IF, Elevation Gain, Calories, Work

**Swim (Natacion)**:
- Duration, Distance (metros), Average Pace (sec/100m), TSS, IF, Calories

**NOTA: Los entrenamientos de Strength (Fuerza) NO estan disponibles actualmente. Si el atleta solicita entrenamientos de fuerza, indicale que esta funcionalidad se agregara proximamente.**

## ESTRUCTURA DE LLAMADA A crear_workout (COMPLETA)

```
crear_workout(
    workout_type="Run",                    # SIEMPRE incluir tipo
    title="Rodaje + Técnica + Strides",    # SIEMPRE incluir titulo
    description="Base aeróbica y técnica", # SIEMPRE incluir descripcion breve
    pre_activity_comments=Estructura:
- Calentamiento: 10-15 min Z1-Z2
- Técnica: 6-8 min drills
- Strides: 4-6 x 20s rápidos
- Rodaje: 25-35 min Z2
- Enfriamiento: 5-10 min Z1

Intensidad: Mantén Z2 en bloque central (~70-78% FCmax),
    planned_values={                       # OBLIGATORIO - SIEMPRE incluir con todos los valores disponibles
        "Duration": "1:00:00",
        "Distance": "10",
        "TSS": "55",
        "IF": "0.75",
        "Elevation Gain": "50",
        "Calories": "500"
    },
    folder_name="Neuronomy",
    click_save=True
)
```

## REGLA DE ORO SOBRE planned_values

- SIN planned_values, los campos numéricos en TrainingPeaks quedan VACIOS
- CON planned_values, TrainingPeaks recibe TODOS los datos correctamente
- SIEMPRE incluye Duration + al menos uno de (Distance, TSS, IF)
- Convierte números a strings con formato correcto:
  - Duration: "h:m:s" (ej: "1:30:00")
  - Distance/Speed/Pace: strings numericos (ej: "12", "5:30")
  - TSS/IF: decimales en strings (ej: "75", "0.85")

## HERRAMIENTAS DISPONIBLES
### Creacion de Workouts
- obtener_esquema_parametros_workout(workout_type): SIEMPRE CONSULTA ESTO PRIMERO
- crear_workout: Crear con TODOS los campos rellenos
- CARPETA POR DEFECTO: "Neuronomy" - Todos los workouts se guardan ahi automaticamente

### Calendario
- listar_workouts_del_dia, navegar_calendario, arrastrar_workout_a_calendario

### Workout Library
- listar_workouts, obtener_datos_workout

## FLUJO DE TRABAJO OBLIGATORIO

1. **PREGUNTAR**: Que tipo de entrenamiento necesita
2. **CONSULTAR**: Llamar a obtener_esquema_parametros_workout(tipo) para ver parametros
3. **PROPONER**: Mostrar estructura + valores planeados con numeros
4. **ESPERAR FEEDBACK**: Pedir confirmacion
5. **CREAR**: Usar crear_workout CON TODOS LOS CAMPOS + planned_values COMPLETO
6. **CONFIRMAR**: El workout fue creado exitosamente

## EJEMPLO DE PROPUESTA COMPLETA AL USUARIO

"Propongo el siguiente entrenamiento:

**Titulo:** Rodaje + Técnica + Strides (General)

**Objetivo:** Construir base aeróbica y mejorar economía sin fatiga

**Estructura:**
- Calentamiento: 10-15 min Z1→Z2 (RPE 3-4/10)
- Técnica: 6-8 min con 4-5 drills
- Strides: 4-6 x 20s rápidos con 40s recuperación
- Bloque aeróbico: 25-35 min Z2 estable
- Enfriamiento: 5-10 min muy suave

**Valores planeados:**
- Duración: 60 minutos
- Distancia: 10 km
- TSS: 55
- IF: 0.75
- Desnivel: 50m

¿Te parece bien o quieres ajustes? Una vez confirmado, lo creo en tu Workout Library."

## REGLAS CRÍTICAS
1. NUNCA crees sin aprobación previa
2. SIEMPRE incluye title, description, pre_activity_comments Y planned_values
3. planned_values debe tener Duration + al menos TSS o Distance
4. Los valores numéricos van en pre_activity_comments (texto) Y en planned_values (numeros)
5. Usa la carpeta "AI Generated" por defecto si el usuario no especifica

Responde siempre en español.
"""
    
    # Limite de iteraciones de tool calls para evitar loops infinitos
    MAX_TOOL_ITERATIONS = 10
    
    def __init__(
        self,
        name: str,
        session_id: str,
        athlete_name: str = "",
        athlete_info: Optional[Dict[str, Any]] = None,
        system_message: Optional[str] = None,
        model: Optional[str] = None,
        initial_history: Optional[List[Dict[str, Any]]] = None,
        use_tools: bool = True,
        **kwargs
    ):
        """
        Inicializa el agente de chat.
        
        Args:
            name: Nombre identificador del agente
            session_id: ID de la sesion de entrenamiento asociada
            athlete_name: Nombre del atleta para contexto
            athlete_info: Informacion adicional del atleta (opcional)
            system_message: Instrucciones del sistema para el agente
            model: Modelo de LLM a utilizar (default: settings.AUTOGEN_MODEL)
            initial_history: Historial previo de mensajes para restaurar
            use_tools: Si True, habilita function calling con herramientas MCP
            **kwargs: Argumentos adicionales para BaseAgent
        """
        # Construir contexto de fecha actual
        now = datetime.now()
        date_context = f"""## CONTEXTO TEMPORAL
Fecha actual: {now.strftime('%A %d de %B de %Y')}
Hora actual: {now.strftime('%H:%M')}
Dia de la semana: {now.strftime('%A')}

"""
        # Traducir dias y meses al español
        day_translations = {
            'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miercoles',
            'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sabado', 'Sunday': 'Domingo'
        }
        month_translations = {
            'January': 'Enero', 'February': 'Febrero', 'March': 'Marzo', 'April': 'Abril',
            'May': 'Mayo', 'June': 'Junio', 'July': 'Julio', 'August': 'Agosto',
            'September': 'Septiembre', 'October': 'Octubre', 'November': 'Noviembre', 'December': 'Diciembre'
        }
        for eng, esp in day_translations.items():
            date_context = date_context.replace(eng, esp)
        for eng, esp in month_translations.items():
            date_context = date_context.replace(eng, esp)
        
        # Construir contexto del atleta
        athlete_context = ""
        if athlete_name:
            athlete_context = f"""## ATLETA ACTUAL
Nombre: {athlete_name}
"""
            # Agregar informacion adicional si esta disponible
            if athlete_info:
                if athlete_info.get("age"):
                    athlete_context += f"Edad: {athlete_info['age']} anos\n"
                if athlete_info.get("discipline"):
                    athlete_context += f"Disciplina: {athlete_info['discipline']}\n"
                if athlete_info.get("level"):
                    athlete_context += f"Nivel: {athlete_info['level']}\n"
                if athlete_info.get("goal"):
                    athlete_context += f"Objetivo: {athlete_info['goal']}\n"
                if athlete_info.get("experience"):
                    athlete_context += f"Experiencia: {athlete_info['experience']}\n"
                # Informacion personal detallada
                personal = athlete_info.get("personal", {})
                if personal:
                    if personal.get("genero"):
                        athlete_context += f"Genero: {personal['genero']}\n"
                    if personal.get("bmi"):
                        athlete_context += f"BMI: {personal['bmi']}\n"
                    if personal.get("tipoAtleta"):
                        athlete_context += f"Tipo de atleta: {personal['tipoAtleta']}\n"
                    if personal.get("sesionesSemanales"):
                        athlete_context += f"Sesiones por semana: {personal['sesionesSemanales']}\n"
                    if personal.get("horasSemanales"):
                        athlete_context += f"Horas por semana: {personal['horasSemanales']}\n"
                    if personal.get("horarioPreferido"):
                        athlete_context += f"Horario preferido: {personal['horarioPreferido']}\n"
                    if personal.get("diaDescanso"):
                        athlete_context += f"Dia de descanso: {personal['diaDescanso']}\n"
                # Informacion medica
                medica = athlete_info.get("medica", {})
                if medica:
                    if medica.get("enfermedades"):
                        athlete_context += f"Condiciones medicas: {medica['enfermedades']}\n"
                    if medica.get("horasSueno"):
                        athlete_context += f"Horas de sueno: {medica['horasSueno']}\n"
                # Informacion deportiva
                deportiva = athlete_info.get("deportiva", {})
                if deportiva:
                    if deportiva.get("eventoObjetivo"):
                        athlete_context += f"Evento objetivo: {deportiva['eventoObjetivo']}\n"
                    if deportiva.get("diasParaEvento"):
                        athlete_context += f"Dias para el evento: {deportiva['diasParaEvento']}\n"
                    if deportiva.get("dedicacion"):
                        athlete_context += f"Dedicacion: {deportiva['dedicacion']}\n"
                    records = deportiva.get("records", {})
                    if records:
                        athlete_context += "Records personales:\n"
                        if records.get("dist5k"):
                            athlete_context += f"  - 5k: {records['dist5k']}\n"
                        if records.get("dist10k"):
                            athlete_context += f"  - 10k: {records['dist10k']}\n"
                        if records.get("dist21k"):
                            athlete_context += f"  - 21k: {records['dist21k']}\n"
                        if records.get("maraton"):
                            athlete_context += f"  - Maraton: {records['maraton']}\n"
            athlete_context += "\n"
        
        # Prepend fecha y atleta al system message
        base_system = system_message or self.DEFAULT_SYSTEM_MESSAGE
        full_system_message = date_context + athlete_context + base_system
        
        super().__init__(
            name=name,
            system_message=full_system_message,
            model=model,
            **kwargs
        )
        
        self.session_id = session_id
        self.use_tools = use_tools
        self._client: Optional[AsyncOpenAI] = None
        self._history: List[ChatMessage] = []
        
        # Cargar historial inicial si se proporciona
        if initial_history:
            self.load_history(initial_history)
    
    async def setup(self) -> None:
        """Inicializa el cliente de OpenAI para el agente."""
        await super().setup()
        
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Verificar disponibilidad de herramientas
        tools_available = MCPToolsAdapter.is_available() if self.use_tools else False
        
        # Log de configuracion del agente
        logger.info(
            f"ChatAgent '{self.name}' inicializado:\n"
            f"  Session: {self.session_id}\n"
            f"  Model: {self.model}\n"
            f"  Temperature: {self.temperature}\n"
            f"  Max tokens: {self.max_tokens}\n"
            f"  Tools enabled: {self.use_tools}\n"
            f"  Tools available: {tools_available}\n"
            f"  API Key configured: {'Yes' if settings.OPENAI_API_KEY else 'NO!'}"
        )
        
        # Log en audit para la sesion
        AuditLogger.log_event(
            session_id=self.session_id,
            event="AGENT_SETUP",
            details={
                "agent_name": self.name,
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "use_tools": self.use_tools,
                "tools_available": tools_available,
                "system_message_length": len(self.system_message)
            }
        )
    
    async def handle_message(self, message: TextMessage, ctx: MessageContext) -> AgentResponse:
        """
        Procesa un mensaje de texto y genera una respuesta.
        Implementacion del metodo abstracto de BaseAgent.
        """
        return await self.process_message(message.content)
    
    async def process_message(self, user_message: str) -> AgentResponse:
        """
        Procesa un mensaje del usuario y genera una respuesta.
        
        Este metodo soporta function calling: si OpenAI solicita ejecutar
        herramientas, las ejecuta y envia los resultados de vuelta.
        
        Args:
            user_message: Texto del mensaje del usuario
            
        Returns:
            AgentResponse: Respuesta del agente con contenido y metadatos
        """
        if not self._client:
            await self.setup()
        
        # Agregar mensaje del usuario al historial
        user_chat_msg = ChatMessage(role="user", content=user_message)
        self._history.append(user_chat_msg)
        
        # Ejecutar loop de conversacion con posibles tool calls
        total_tool_calls = 0
        iteration = 0
        
        while iteration < self.MAX_TOOL_ITERATIONS:
            iteration += 1
            
            # Construir mensajes para la API
            messages = self._build_api_messages()
            
            try:
                # Construir parametros de la llamada
                api_params = self._build_api_params(messages)
                
                # LOG: Registrar request a OpenAI
                self._log_openai_request(api_params, iteration)
                
                # Llamar a la API de OpenAI
                response = await self._client.chat.completions.create(**api_params)
                
                # LOG: Registrar response de OpenAI
                self._log_openai_response(response, iteration)
                
                choice = response.choices[0]
                message = choice.message
                
                # Verificar si hay tool calls
                if message.tool_calls:
                    # Agregar mensaje del asistente con tool calls al historial
                    tool_calls_data = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                    
                    assistant_msg = ChatMessage(
                        role="assistant",
                        content=message.content or "",
                        tool_calls=tool_calls_data
                    )
                    self._history.append(assistant_msg)
                    
                    # Ejecutar cada herramienta
                    for tool_call in message.tool_calls:
                        total_tool_calls += 1
                        tool_result = await self._execute_tool_call(tool_call)
                        
                        # Agregar resultado al historial
                        tool_msg = ChatMessage(
                            role="tool",
                            content=tool_result,
                            tool_call_id=tool_call.id
                        )
                        self._history.append(tool_msg)
                    
                    # Continuar el loop para obtener respuesta final
                    continue
                
                # No hay tool calls, esta es la respuesta final
                response_content = message.content or ""
                
                # Si la respuesta esta vacia, loguear warning
                if not response_content:
                    self._log_empty_response(response)
                
                # Agregar respuesta al historial
                assistant_msg = ChatMessage(role="assistant", content=response_content)
                self._history.append(assistant_msg)
                
                logger.debug(
                    f"ChatAgent '{self.name}': Procesado mensaje. "
                    f"Historial: {len(self._history)} mensajes, "
                    f"Tool calls: {total_tool_calls}"
                )
                
                return AgentResponse(
                    content=response_content,
                    agent_name=self.name,
                    metadata={
                        "session_id": self.session_id,
                        "model": self.model,
                        "history_length": len(self._history),
                        "timestamp": datetime.utcnow().isoformat(),
                        "finish_reason": choice.finish_reason,
                        "tool_calls_executed": total_tool_calls,
                        "iterations": iteration,
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                            "completion_tokens": response.usage.completion_tokens if response.usage else 0
                        }
                    }
                )
                
            except Exception as e:
                logger.error(f"Error en ChatAgent '{self.name}': {e}")
                AuditLogger.log_error(
                    session_id=self.session_id,
                    error_type="OPENAI_ERROR",
                    message=str(e),
                    details={"model": self.model, "iteration": iteration}
                )
                raise
        
        # Se alcanzo el limite de iteraciones
        error_msg = f"Se alcanzo el limite de {self.MAX_TOOL_ITERATIONS} iteraciones de herramientas"
        logger.warning(f"ChatAgent '{self.name}': {error_msg}")
        
        return AgentResponse(
            content=error_msg,
            agent_name=self.name,
            metadata={
                "session_id": self.session_id,
                "error": "max_iterations_reached",
                "tool_calls_executed": total_tool_calls
            }
        )
    
    def _build_api_params(self, messages: List[Dict]) -> Dict[str, Any]:
        """Construye los parametros para la llamada a OpenAI."""
        api_params = {
            "model": self.model,
            "messages": messages,
        }
        
        # Detectar tipo de modelo
        is_reasoning_model = (
            self.model.startswith("o1") or 
            self.model.startswith("gpt-5")
        )
        
        is_new_model = (
            self.model.startswith("gpt-4o") or
            "gpt-4o" in self.model
        )
        
        # Temperature (no soportado en modelos de razonamiento)
        if not is_reasoning_model:
            api_params["temperature"] = self.temperature
        
        # Max tokens
        if is_reasoning_model:
            pass  # Sin limite para modelos de razonamiento
        elif is_new_model:
            api_params["max_completion_tokens"] = self.max_tokens
        else:
            api_params["max_tokens"] = self.max_tokens
        
        # Agregar herramientas si estan habilitadas y disponibles
        if self.use_tools and MCPToolsAdapter.is_available():
            tools = MCPToolsAdapter.get_openai_tools()
            if tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = "auto"
        
        return api_params
    
    async def _execute_tool_call(self, tool_call) -> str:
        """Ejecuta una herramienta y retorna el resultado."""
        function_name = tool_call.function.name
        
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            arguments = {}
        
        logger.info(
            f"ChatAgent '{self.name}': Ejecutando herramienta {function_name} "
            f"con args: {arguments}"
        )
        
        # Log de la herramienta
        AuditLogger.log_mcp_call(
            session_id=self.session_id,
            action=f"TOOL_CALL_{function_name.upper()}",
            details={"arguments": arguments},
            success=True
        )
        
        # Ejecutar la herramienta
        result = MCPToolsAdapter.execute_tool(
            tool_name=function_name,
            arguments=arguments,
            session_id=self.session_id
        )
        
        logger.info(
            f"ChatAgent '{self.name}': Herramienta {function_name} completada. "
            f"Resultado: {len(result)} chars"
        )
        
        return result
    
    def _log_openai_request(self, api_params: Dict[str, Any], iteration: int = 1) -> None:
        """Registra la request enviada a OpenAI."""
        log_params = api_params.copy()
        
        # Truncar mensajes
        if "messages" in log_params:
            log_messages = []
            for msg in log_params["messages"]:
                content = msg.get("content", "") or ""
                truncated = content[:200] + "..." if len(content) > 200 else content
                log_msg = {"role": msg.get("role"), "content": truncated}
                if msg.get("tool_calls"):
                    log_msg["tool_calls"] = f"[{len(msg['tool_calls'])} calls]"
                if msg.get("tool_call_id"):
                    log_msg["tool_call_id"] = msg["tool_call_id"]
                log_messages.append(log_msg)
            log_params["messages"] = log_messages
            log_params["message_count"] = len(api_params["messages"])
        
        # Info de tokens
        if "max_completion_tokens" in log_params:
            max_tokens_info = f"max_completion_tokens: {log_params.get('max_completion_tokens')}"
        elif "max_tokens" in log_params:
            max_tokens_info = f"max_tokens: {log_params.get('max_tokens')}"
        else:
            max_tokens_info = "unlimited (reasoning model)"
        
        # Info de herramientas
        tools_info = f"{len(log_params.get('tools', []))} tools" if "tools" in log_params else "no tools"
        
        logger.info(
            f"ChatAgent '{self.name}' -> OpenAI REQUEST (iter {iteration}):\n"
            f"  Model: {log_params.get('model')}\n"
            f"  Messages: {log_params.get('message_count', 0)}\n"
            f"  Temperature: {log_params.get('temperature', 'default')}\n"
            f"  Tokens: {max_tokens_info}\n"
            f"  Tools: {tools_info}"
        )
        
        AuditLogger.log_mcp_call(
            session_id=self.session_id,
            action="OPENAI_REQUEST",
            details={
                "iteration": iteration,
                "model": log_params.get("model"),
                "message_count": log_params.get("message_count", 0),
                "temperature": log_params.get("temperature"),
                "max_tokens": log_params.get("max_completion_tokens") or log_params.get("max_tokens") or "unlimited",
                "tools_count": len(log_params.get("tools", [])),
                "messages_preview": log_params.get("messages", [])[:3]  # Solo primeros 3
            },
            success=True
        )
    
    def _log_openai_response(self, response: Any, iteration: int = 1) -> None:
        """Registra la response recibida de OpenAI."""
        choice = response.choices[0] if response.choices else None
        message = choice.message if choice else None
        content = message.content if message else None
        tool_calls = message.tool_calls if message else None
        
        content_preview = ""
        if content:
            content_preview = content[:300] + "..." if len(content) > 300 else content
        
        tool_calls_info = f"{len(tool_calls)} tool calls" if tool_calls else "no tool calls"
        
        logger.info(
            f"ChatAgent '{self.name}' <- OpenAI RESPONSE (iter {iteration}):\n"
            f"  Model: {response.model}\n"
            f"  Finish reason: {choice.finish_reason if choice else 'N/A'}\n"
            f"  Content length: {len(content) if content else 0} chars\n"
            f"  Tool calls: {tool_calls_info}\n"
            f"  Prompt tokens: {response.usage.prompt_tokens if response.usage else 0}\n"
            f"  Completion tokens: {response.usage.completion_tokens if response.usage else 0}"
        )
        
        AuditLogger.log_mcp_call(
            session_id=self.session_id,
            action="OPENAI_RESPONSE",
            details={
                "iteration": iteration,
                "model": response.model,
                "finish_reason": choice.finish_reason if choice else None,
                "content_length": len(content) if content else 0,
                "content_preview": content_preview,
                "has_tool_calls": bool(tool_calls),
                "tool_calls_count": len(tool_calls) if tool_calls else 0,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                }
            },
            success=bool(content or tool_calls)
        )
    
    def _log_empty_response(self, response: Any) -> None:
        """Loguea una respuesta vacia."""
        choice = response.choices[0] if response.choices else None
        
        logger.warning(
            f"ChatAgent '{self.name}': Respuesta vacia de OpenAI. "
            f"finish_reason: {choice.finish_reason if choice else 'N/A'}, "
            f"model: {response.model}"
        )
        
        AuditLogger.log_error(
            session_id=self.session_id,
            error_type="EMPTY_RESPONSE",
            message="OpenAI retorno respuesta vacia",
            details={
                "finish_reason": choice.finish_reason if choice else None,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0
                }
            }
        )
    
    def _build_api_messages(self) -> List[Dict[str, Any]]:
        """
        Construye la lista de mensajes para enviar a la API.
        Incluye el system message y todo el historial.
        """
        messages = [{"role": "system", "content": self.system_message}]
        messages.extend([msg.to_openai_format() for msg in self._history])
        return messages
    
    def load_history(self, history: List[Dict[str, Any]]) -> None:
        """
        Carga un historial de mensajes previo.
        Util para restaurar conversaciones desde la base de datos.
        """
        self._history = [ChatMessage.from_dict(msg) for msg in history]
        logger.info(
            f"ChatAgent '{self.name}': Cargados {len(self._history)} mensajes previos"
        )
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de conversacion como lista de diccionarios.
        Formato listo para persistir en base de datos.
        """
        return [msg.to_dict() for msg in self._history]
    
    def clear_history(self) -> None:
        """Limpia el historial de conversacion."""
        self._history = []
        logger.info(f"ChatAgent '{self.name}': Historial limpiado")
    
    def get_message_count(self) -> int:
        """Retorna la cantidad de mensajes en el historial."""
        return len(self._history)
    
    def update_system_message(self, new_system_message: str) -> None:
        """Actualiza el mensaje de sistema del agente."""
        self.system_message = new_system_message
        logger.info(f"ChatAgent '{self.name}': System message actualizado")
    
    def get_config(self) -> Dict[str, Any]:
        """Obtiene la configuracion actual del agente."""
        config = super().get_config()
        config.update({
            "session_id": self.session_id,
            "history_length": len(self._history),
            "use_tools": self.use_tools,
        })
        return config
