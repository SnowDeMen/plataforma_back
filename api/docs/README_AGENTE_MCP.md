# Agente MCP con Function Calling Automático

Sistema completo de agente con integración de herramientas MCP de TrainingPeaks usando OpenAI function calling.

## Características

- **Function Calling Automático**: El agente ejecuta herramientas MCP automáticamente según la conversación
- **21 Herramientas de TrainingPeaks**: Acceso completo a workouts, calendario y gestión de atletas
- **Conversación Natural**: Habla con el agente en lenguaje natural y él ejecutará las acciones necesarias
- **Manejo Inteligente de Errores**: El agente maneja errores y reintenta cuando es necesario

## Requisitos

1. **Python 3.13+**
2. **Dependencias instaladas**:
   ```bash
   pip install -r requirements.txt
   ```

3. **API Key de OpenAI** configurada en `.env`:
   ```bash
   OPENAI_API_KEY=tu-api-key-aqui
   ```

4. **Servidor MCP de TrainingPeaks** corriendo en otra terminal

## Scripts Disponibles

### 1. `agente_mcp_completo.py` - Agente Interactivo Completo

Agente con conversación interactiva que ejecuta herramientas automáticamente.

```bash
python agente_mcp_completo.py
```

**Características**:
- Conversación interactiva (puedes hacer múltiples preguntas)
- Ejecuta herramientas automáticamente
- Muestra cada paso de ejecución
- Mantiene contexto de conversación

**Ejemplo de uso**:
```
Tu mensaje: Lista los workouts de la biblioteca Zwift
[El agente ejecuta automáticamente: abrir_workout_library, listar_workouts]
Respuesta: "Encontré 15 workouts en la biblioteca Zwift: ..."
```

### 2. `agente_mcp_simple.py` - Agente de Una Pregunta

Agente simple para una sola pregunta/tarea.

```bash
python agente_mcp_simple.py
```

**Características**:
- Una pregunta, una respuesta
- Ejecución rápida
- Ideal para scripts automatizados

**Para personalizar**: Edita la variable `mensaje` en la función `main()`.

### 3. `chat_con_agente.py` - Chat Básico (SIN MCP)

Chat simple con el agente sin herramientas MCP.

```bash
python chat_con_agente.py
```

## Herramientas MCP Disponibles

El agente tiene acceso a 21 herramientas:

### Gestión de Sesión
- `inicializar_sesion()` - Inicia sesión en TrainingPeaks
- `cerrar_sesion()` - Cierra la sesión

### Workout Library
- `abrir_workout_library()` - Abre el panel de workouts
- `expandir_library(nombre_library)` - Expande una biblioteca
- `listar_workouts(nombre_library)` - Lista workouts de una biblioteca
- `subir_workout(ruta_archivo, nombre_library)` - Sube un workout
- `eliminar_workout(nombre_workout, nombre_library)` - Elimina un workout
- `obtener_datos_workout(nombre_workout, nombre_library)` - Obtiene datos de un workout
- `arrastrar_workout_a_calendario(nombre_workout, fecha_destino)` - Arrastra workout al calendario

### Calendario
- `navegar_calendario(accion)` - Navega por el calendario (adelante/atras/hoy)
- `clickear_fecha_calendario(fecha)` - Navega a una fecha específica
- `clickear_workout_en_calendario(fecha, nombre_workout)` - Hace clic en un workout
- `obtener_datos_calendario()` - Obtiene datos del Quick View
- `cerrar_quickview_calendario()` - Cierra el Quick View
- `listar_workouts_del_dia(fecha)` - Lista workouts de un día
- `verificar_workouts_en_fecha(fecha)` - Verifica si hay workouts en una fecha

### Athlete Library
- `abrir_athlete_library()` - Abre el panel de atletas
- `expandir_todas_athlete_libraries()` - Expande todas las carpetas de atletas
- `seleccionar_atleta(nombre_atleta)` - Selecciona un atleta

### Utilidades
- `obtener_estado_paneles()` - Obtiene el estado de los paneles
- `guardar_archivo_local(nombre_archivo, contenido, ruta_destino)` - Guarda un archivo local

## Ejemplos de Uso

### Ejemplo 1: Listar Workouts

```python
mensaje = "Lista todos los workouts de la biblioteca Zwift"
```

**El agente ejecutará automáticamente**:
1. `abrir_workout_library()`
2. `listar_workouts(nombre_library="Zwift")`

### Ejemplo 2: Consultar Entrenamientos de una Semana

```python
mensaje = """
Necesito ver los entrenamientos de Luis Aragon de los últimos 7 días.
Por cada día, dime qué workouts tiene programados.
"""
```

**El agente ejecutará automáticamente**:
1. `abrir_athlete_library()`
2. `seleccionar_atleta(nombre_atleta="Luis Aragon")`
3. `navegar_calendario(accion="hoy")`
4. Para cada día: `listar_workouts_del_dia(fecha="YYYY-MM-DD")`

### Ejemplo 3: Programar un Workout

```python
mensaje = """
Arrastra el workout "FTP Test" de la biblioteca Zwift 
al calendario el día 2025-11-25
"""
```

**El agente ejecutará automáticamente**:
1. `abrir_workout_library()`
2. `arrastrar_workout_a_calendario(nombre_workout="FTP Test", fecha_destino="2025-11-25")`

## Arquitectura

```
app/
├── agents/
│   ├── test_agent.py          # Agente básico (sin function calling)
│   └── mcp_agent.py            # Agente con function calling automático ✨
├── infrastructure/
│   ├── autogen/
│   │   └── generic_mcp_agent.py
│   └── mcp/
│       ├── mcp_client.py       # Cliente MCP básico
│       └── mcp_tools_wrapper.py # Wrapper para OpenAI function calling ✨
└── core/
    └── config.py

Scripts de uso:
├── agente_mcp_completo.py      # Agente interactivo completo ✨
├── agente_mcp_simple.py        # Agente simple de una pregunta ✨
├── chat_con_agente.py          # Chat básico sin MCP
└── use_test_agent.py           # Script de configuración básica
```

## Cómo Funciona

1. **Conexión**: El agente se conecta al servidor MCP de TrainingPeaks
2. **Obtención de Herramientas**: Obtiene las 21 herramientas disponibles
3. **Conversión**: Convierte las herramientas MCP al formato de OpenAI function calling
4. **Chat**: El usuario envía un mensaje
5. **Function Calling**: OpenAI decide qué herramientas ejecutar
6. **Ejecución**: El agente ejecuta las herramientas en el servidor MCP
7. **Respuesta**: El agente procesa los resultados y responde al usuario

## Output del Agente

El agente muestra cada paso de ejecución:

```
[Iteración 1] Llamando al modelo...
[Iteración 1] Ejecutando 2 herramienta(s)...
  - abrir_workout_library({})
    Resultado: [OK] Workout Library abierta
  - listar_workouts({"nombre_library": "Zwift"})
    Resultado: {"library": "Zwift", "total": 15, "workouts": [...]}

[Iteración 2] Llamando al modelo...

======================================================================
RESPUESTA FINAL
======================================================================

Encontré 15 workouts en la biblioteca Zwift:
1. FTP Test - 60 minutos
2. Sweet Spot Intervals - 90 minutos
...
```

## Configuración Avanzada

### Cambiar el System Message

Edita el `system_message` en el script para personalizar el comportamiento del agente:

```python
system_message = """Eres un asistente experto en TrainingPeaks.
Tu objetivo es ayudar a analizar entrenamientos y optimizar planes.
Siempre confirma las acciones antes de ejecutarlas."""
```

### Cambiar el Modelo de OpenAI

Por defecto usa `gpt-4`. Para cambiar:

```python
agent = MCPAgent(
    name="trainingpeaks",
    system_message=system_message,
    model="gpt-4o"  # o "gpt-3.5-turbo", etc.
)
```

### Limitar Iteraciones

Por defecto permite 10 iteraciones de function calling. Para cambiar:

```python
respuesta = await agent.chat(mensaje, max_iterations=5)
```

## Troubleshooting

### Error: "Unable to obtain driver for chrome"

**Causa**: El servidor MCP no puede acceder a Chrome/ChromeDriver.

**Solución**: Asegúrate de que el servidor MCP de TrainingPeaks esté corriendo correctamente en otra terminal con Chrome disponible.

### Error: "No hay conexión con el servidor MCP"

**Causa**: El agente no se conectó al servidor MCP.

**Solución**: Verifica que la ruta al servidor MCP sea correcta en el script.

### El agente no ejecuta herramientas

**Causa**: Puede ser un problema con el system message o el modelo.

**Solución**: 
1. Verifica que el system message indique claramente que debe usar herramientas
2. Usa un modelo que soporte function calling (gpt-4, gpt-3.5-turbo, etc.)

## Próximos Pasos

- [ ] Agregar streaming de respuestas
- [ ] Implementar caché de herramientas
- [ ] Agregar logs detallados
- [ ] Crear interfaz web
- [ ] Agregar más validaciones de parámetros

## Soporte

Para preguntas o problemas, revisa:
1. Los logs del servidor MCP
2. Los mensajes de error del agente
3. La configuración de `.env`

