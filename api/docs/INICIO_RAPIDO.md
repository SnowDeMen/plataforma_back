# Inicio Rápido: Agente MCP

## 🚀 Uso en 3 Pasos

### 1. Asegúrate de tener todo configurado

```bash
# API Key en .env
OPENAI_API_KEY=tu-api-key-aqui

# Servidor MCP corriendo en otra terminal
python trainingpeaks_mcp_server_modular.py
```

### 2. Ejecuta el agente

```bash
python agente_mcp_completo.py
```

### 3. Haz preguntas en lenguaje natural

```
Tu mensaje: Lista los workouts de la biblioteca Zwift

[El agente ejecuta automáticamente las herramientas necesarias]

Respuesta: Encontré 15 workouts en la biblioteca Zwift: ...
```

## 💬 Ejemplos de Preguntas

### Consultar Workouts
```
"Lista todos los workouts de la biblioteca Zwift"
"¿Cuántos workouts hay en total en mi biblioteca?"
"Muéstrame los detalles del workout 'FTP Test'"
```

### Consultar Calendario
```
"¿Qué entrenamientos tiene Luis Aragon programados para hoy?"
"Muéstrame los workouts de los próximos 7 días"
"¿Hay algún entrenamiento programado para el 25 de noviembre?"
```

### Gestionar Workouts
```
"Arrastra el workout 'FTP Test' al calendario el 25 de noviembre"
"Elimina el workout 'Old Workout' de la biblioteca Zwift"
"Sube el archivo intervals.zwo a la biblioteca Zwift"
```

### Consultar Estado
```
"¿Qué paneles están abiertos ahora?"
"Muéstrame el estado actual de la interfaz"
```

## 📋 Scripts Disponibles

| Script | Uso | Descripción |
|--------|-----|-------------|
| `agente_mcp_completo.py` | ⭐ Principal | Agente interactivo completo |
| `agente_mcp_simple.py` | Una pregunta | Ejecución rápida |
| `demo_completa.py` | Demostración | Muestra todas las capacidades |
| `chat_con_agente.py` | Sin MCP | Chat básico sin herramientas |

## 🎯 Lo Que el Agente Hace Automáticamente

Cuando le dices: **"Lista los workouts de Zwift"**

El agente ejecuta automáticamente:
1. `abrir_workout_library()` - Abre el panel
2. `listar_workouts(nombre_library="Zwift")` - Lista los workouts
3. Procesa los resultados
4. Te responde en lenguaje natural

**¡Todo sin que tengas que especificar qué herramientas usar!**

## 🔧 Personalización Rápida

### Cambiar el mensaje inicial

Edita `agente_mcp_simple.py`:

```python
mensaje = "Tu pregunta aquí"
```

### Cambiar el comportamiento del agente

Edita el `system_message` en cualquier script:

```python
system_message = """Eres un asistente que...
- Hace esto
- Hace aquello
"""
```

## 📖 Documentación Completa

- **README_AGENTE_MCP.md** - Documentación completa
- **RESUMEN_IMPLEMENTACION.md** - Detalles técnicos
- **INICIO_RAPIDO.md** - Este archivo

## ❓ Problemas Comunes

### "Unable to obtain driver for chrome"
- Asegúrate de que el servidor MCP esté corriendo
- Verifica que Chrome/ChromeDriver estén instalados

### "No hay conexión con el servidor MCP"
- Verifica la ruta al servidor MCP en el script
- Asegúrate de que el servidor esté corriendo

### El agente no ejecuta herramientas
- Verifica que tengas una API key válida
- Usa un modelo que soporte function calling (gpt-4, gpt-3.5-turbo)

## 🎉 ¡Listo!

Ya puedes usar el agente para gestionar TrainingPeaks mediante conversación natural.

```bash
python agente_mcp_completo.py
```

**¡Disfruta!** 🚀

