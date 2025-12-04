"""
Servidor MCP para automatizacion de TrainingPeaks - Version Modular

Permite gestionar workouts y calendario mediante herramientas MCP.
Requiere que se inyecte un driver de Selenium ya inicializado
con la sesion activa y el atleta seleccionado.

Uso:
    from domain.core import set_driver
    set_driver(mi_driver_externo)
    
    # Ahora el MCP puede usar todas las funciones
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from selenium.common.exceptions import TimeoutException
import os
from typing import Dict, Any, Optional, List

# Importar modulos del dominio
from domain.core import set_driver, is_driver_ready, get_driver
from domain.workout_library import (
    workout_library,
    is_workout_library_open,
    workout_folder,
    manage_workout,
    list_workouts_in_library,
    create_workout
)
from domain.calendar import (
    week_forward,
    week_backward,
    calendar_go_to_today,
    click_calendar_date_until,
    drag_workout_to_calendar,
    get_all_quickviews_on_date
)


# ============================================================================
# ESQUEMA DE PARAMETROS PARA CREACION DE WORKOUTS
# ============================================================================
# Este esquema define que parametros estan disponibles para cada tipo de workout
# en TrainingPeaks. El agente debe consultarlo ANTES de crear un workout.

WORKOUT_PARAMETERS_SCHEMA: Dict[str, Any] = {
    "parameter_definitions": {
        "Duration": {
            "description": "Duracion total del entrenamiento en formato h:m:s",
            "format": "h:m:s",
            "example": "1:30:00"
        },
        "Distance": {
            "description": "Distancia total a recorrer",
            "units": "km (run/bike) o m (swim)",
            "example": "10"
        },
        "Average Pace": {
            "description": "Ritmo promedio objetivo",
            "format": "min/km (run) o sec/100m (swim)",
            "example": "5:30"
        },
        "Average Speed": {
            "description": "Velocidad promedio objetivo",
            "units": "kph",
            "example": "25"
        },
        "Calories": {
            "description": "Gasto calorico estimado",
            "units": "kcal",
            "example": "500"
        },
        "Elevation Gain": {
            "description": "Desnivel positivo acumulado",
            "units": "m",
            "example": "200"
        },
        "TSS": {
            "description": "Training Stress Score - carga de entrenamiento (100 TSS = 1 hora a umbral)",
            "example": "80"
        },
        "IF": {
            "description": "Intensity Factor - intensidad relativa al umbral (1.0 = umbral)",
            "example": "0.85"
        },
        "Work": {
            "description": "Trabajo mecanico realizado",
            "units": "kJ",
            "example": "800"
        }
    },
    "workout_type_parameters": {
        "Day off": ["Duration"],
        "Strength": ["Duration", "Calories", "TSS", "IF"],
        "Crosstrain": ["Duration", "Distance", "Calories", "TSS", "IF"],
        "Custom": ["Duration", "Distance", "Calories", "TSS", "IF"],
        "Other": ["Duration", "Distance", "Calories", "TSS", "IF"],
        "Walk": ["Duration", "Distance", "Average Pace", "Calories", "Elevation Gain", "TSS", "IF"],
        "XC-Ski": ["Duration", "Distance", "Average Pace", "Calories", "Elevation Gain", "TSS", "IF"],
        "Run": ["Duration", "Distance", "Average Pace", "Elevation Gain", "Calories", "TSS", "IF", "Work"],
        "Bike": ["Duration", "Distance", "Average Speed", "Calories", "Elevation Gain", "TSS", "IF", "Work"],
        "Mtn Bike": ["Duration", "Distance", "Average Speed", "Average Pace", "Calories", "Elevation Gain", "TSS", "IF", "Work"],
        "Swim": ["Duration", "Distance", "Average Pace", "Calories", "TSS", "IF"],
        "Rowing": ["Duration", "Distance", "Average Pace", "Calories", "Elevation Gain", "TSS", "IF"],
        "Brick": ["Duration", "Distance", "Average Speed", "Average Pace", "Calories", "Elevation Gain", "TSS", "IF", "Work"]
    },
    "available_workout_types": [
        "Run", "Bike", "Swim", "Strength", "Walk", "Rowing",
        "Mtn Bike", "XC-Ski", "Brick", "Crosstrain", "Custom", "Other", "Day off"
    ]
}


def inicializar_con_driver(driver, wait=None, default_timeout: int = 10):
    """
    Inicializa el MCP con un driver de Selenium externo.
    
    Esta funcion debe llamarse antes de ejecutar el servidor MCP.
    El driver debe estar ya inicializado con:
    - Sesion activa en TrainingPeaks
    - Atleta seleccionado
    - Pagina del calendario cargada
    
    Args:
        driver: Instancia de WebDriver de Selenium ya inicializada
        wait: WebDriverWait ya configurado (opcional)
        default_timeout: Timeout por defecto si no se proporciona wait
        
    Example:
        from selenium import webdriver
        from trainingpeaks_mcp_server_modular import inicializar_con_driver, mcp
        
        # Crear y preparar el driver externamente
        driver = webdriver.Chrome()
        driver.get('https://app.trainingpeaks.com')
        # ... login, seleccionar atleta, etc ...
        
        # Inyectar el driver al MCP
        inicializar_con_driver(driver)
        
        # Ejecutar el servidor
        mcp.run()
    """
    set_driver(driver, wait, default_timeout)


# ============================================================================
# SERVIDOR MCP CON FASTMCP
# ============================================================================

# Inicializar servidor MCP
mcp = FastMCP("TrainingPeaks Automation Server")


# ----------------------------------------------------------------------------
# HERRAMIENTAS MCP PARA WORKOUT LIBRARY
# ----------------------------------------------------------------------------

@mcp.tool()
def abrir_workout_library() -> str:
    """
    Abre el panel de Workout Library.
    
    IMPORTANTE: Solo llama esta funcion si necesitas abrir el panel explicitamente.
    Las demas funciones de workout library ya manejan la apertura automaticamente.
    No es necesario llamar esta funcion antes de expandir_library, listar_workouts, etc.
    
    Returns:
        Mensaje de confirmacion o error
    """
    try:
        workout_library()
        return "[OK] Workout Library abierta"
    except Exception as e:
        return f"[ERROR] Error al abrir Workout Library: {str(e)}"


@mcp.tool()
def expandir_library(nombre_library: str, exact: bool = True) -> str:
    """
    Expande una Workout Library especifica.
    Esta funcion abre automaticamente el panel de Workout Library si esta cerrado.
    
    Args:
        nombre_library: Nombre de la library a expandir
        exact: Si True, busca match exacto del nombre
        
    Returns:
        Mensaje de confirmacion o error
        
    Nota: No necesitas llamar abrir_workout_library() antes de esta funcion.
    """
    try:
        workout_library()
        workout_folder(nombre_library, exact=exact)
        return f"[OK] Library '{nombre_library}' expandida correctamente"
    except TimeoutException as e:
        if "No se encontro" in str(e):
            return f"[ERROR] No se encontro la library '{nombre_library}'"
        return f"[ERROR] Error: {str(e)}"
    except Exception as e:
        return f"[ERROR] Error al expandir library: {str(e)}"


@mcp.tool()
def listar_workouts(nombre_library: str, exact: bool = False) -> Dict[str, Any]:
    """
    Lista todos los workouts disponibles en una Workout Library especifica.
    
    Args:
        nombre_library: Nombre (o parte del nombre) de la library a listar 
        exact: Si True, busca match exacto del nombre
        
    Returns:
        Dict con la lista de workouts y el total encontrado
    """
    try:
        workout_library()
        workouts = list_workouts_in_library(nombre_library, exact=exact)
        
        if not workouts:
            return {
                "library": nombre_library,
                "total": 0,
                "workouts": [],
                "mensaje": f"No se encontraron workouts en '{nombre_library}'"
            }
        
        return {
            "library": nombre_library,
            "total": len(workouts),
            "workouts": workouts,
            "mensaje": f"[OK] {len(workouts)} workouts encontrados en '{nombre_library}'"
        }
    except Exception as e:
        return {
            "library": nombre_library,
            "total": 0,
            "workouts": [],
            "error": f"Error: {str(e)}"
        }


@mcp.tool()
def eliminar_workout(nombre_workout: str, nombre_library: str) -> str:
    """
    Elimina un workout de una Workout Library.
    
    Args:
        nombre_workout: Nombre del workout a eliminar
        nombre_library: Nombre de la library donde esta el workout
        
    Returns:
        Mensaje de confirmacion o error
    """
    try:
        manage_workout(nombre_library, nombre_workout, "delete")
        return f"[OK] Workout '{nombre_workout}' eliminado de '{nombre_library}'"
    except Exception as e:
        return f"[ERROR] Error al eliminar workout: {str(e)}"


@mcp.tool()
def obtener_datos_workout(nombre_workout: str, nombre_library: str) -> Dict[str, Any]:
    """
    Obtiene todos los datos de un workout (metricas, descripcion, estructura, etc).
    
    Args:
        nombre_workout: Nombre del workout
        nombre_library: Nombre de la library donde esta el workout
        
    Returns:
        Dict con todos los datos del workout
    """
    try:
        data = manage_workout(nombre_library, nombre_workout, "data")
        return data if data else {"error": "No se pudieron obtener los datos"}
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


@mcp.tool()
def arrastrar_workout_a_calendario(nombre_workout: str, fecha_destino: str, 
                                   nombre_library: str = None) -> str:
    """
    Arrastra un workout al calendario en una fecha especifica.
    
    Args:
        nombre_workout: Nombre del workout a arrastrar
        fecha_destino: Fecha destino en formato YYYY-MM-DD
        nombre_library: Nombre de la library donde esta el workout (opcional)
        
    Returns:
        Mensaje de confirmacion o error
    """
    try:
        workout_library()
        drag_workout_to_calendar(nombre_workout, fecha_destino, folder=nombre_library, use_today=True)
        return f"[OK] Workout '{nombre_workout}' arrastrado a {fecha_destino}"
    except Exception as e:
        return f"[ERROR] Error al arrastrar workout: {str(e)}"


@mcp.tool()
def obtener_estado_paneles() -> Dict[str, Any]:
    """
    Obtiene el estado actual del panel de Workout Library.
    Util para verificar si esta abierto antes de realizar acciones.
    
    Returns:
        Dict con el estado del panel
    """
    try:
        workout_open = is_workout_library_open()
        
        return {
            "workout_library": {
                "abierto": workout_open,
                "estado": "[OK] Abierto" if workout_open else "[CLOSED] Cerrado"
            },
            "mensaje": "Estado del panel obtenido correctamente"
        }
    except Exception as e:
        return {
            "error": f"Error al obtener estado: {str(e)}"
        }


# ----------------------------------------------------------------------------
# HERRAMIENTAS MCP PARA CREACION DE WORKOUTS
# ----------------------------------------------------------------------------

@mcp.tool()
def obtener_esquema_parametros_workout(workout_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene el esquema de parametros disponibles para crear workouts en TrainingPeaks.
    
    IMPORTANTE: Consulta esta herramienta ANTES de llamar a crear_workout() para saber
    que parametros puedes usar segun el tipo de workout.
    
    Args:
        workout_type: Tipo de workout especifico (Run, Bike, Swim, etc.) o None para ver todos
        
    Returns:
        Dict con:
        - Si workout_type es especificado: parametros disponibles para ese tipo
        - Si workout_type es None: esquema completo con todos los tipos y parametros
        
    Ejemplo:
        # Ver parametros para Run
        obtener_esquema_parametros_workout("Run")
        # Retorna: {"workout_type": "Run", "parameters": ["Duration", "Distance", ...]}
        
        # Ver todos los tipos disponibles
        obtener_esquema_parametros_workout()
    """
    if workout_type:
        # Normalizar el tipo
        workout_type_normalized = workout_type.strip()
        
        # Buscar el tipo (case insensitive)
        type_map = {t.lower(): t for t in WORKOUT_PARAMETERS_SCHEMA["workout_type_parameters"].keys()}
        
        if workout_type_normalized.lower() in type_map:
            actual_type = type_map[workout_type_normalized.lower()]
            params = WORKOUT_PARAMETERS_SCHEMA["workout_type_parameters"][actual_type]
            
            # Incluir definiciones de cada parametro
            param_details = []
            for param_name in params:
                param_def = WORKOUT_PARAMETERS_SCHEMA["parameter_definitions"].get(param_name, {})
                param_details.append({
                    "name": param_name,
                    **param_def
                })
            
            return {
                "workout_type": actual_type,
                "parameters": params,
                "parameter_details": param_details,
                "mensaje": f"[OK] {len(params)} parametros disponibles para {actual_type}"
            }
        else:
            return {
                "error": f"Tipo de workout '{workout_type}' no encontrado",
                "tipos_disponibles": WORKOUT_PARAMETERS_SCHEMA["available_workout_types"]
            }
    else:
        # Retornar esquema completo
        return {
            "tipos_disponibles": WORKOUT_PARAMETERS_SCHEMA["available_workout_types"],
            "parametros_por_tipo": WORKOUT_PARAMETERS_SCHEMA["workout_type_parameters"],
            "definiciones_parametros": WORKOUT_PARAMETERS_SCHEMA["parameter_definitions"],
            "mensaje": "[OK] Esquema completo de parametros para workouts"
        }


@mcp.tool()
def crear_workout(
    workout_type: str = "Run",
    title: Optional[str] = None,
    description: Optional[str] = None,
    pre_activity_comments: Optional[str] = None,
    planned_values: Optional[Dict[str, str]] = None,
    folder_name: str = "Neuronomy",
    click_save: bool = True) -> str:
    """
    Crea un workout directamente en TrainingPeaks dentro de la Workout Library.
    
    CRITICO: planned_values es OBLIGATORIO y debe contener los valores numericos
    que se rellenaran en TrainingPeaks. Sin esto, los campos quedan vacios.
    
    Esta funcion abre el modal de creacion, completa TODOS los campos especificados
    y guarda el workout automaticamente.
    
    Args:
        workout_type: Tipo de workout. Opciones: Run, Bike, Swim, Strength, Walk, 
                      Rowing, Mtn Bike, XC-Ski, Brick, Crosstrain, Custom, Other, Day off
        title: Titulo del workout (ej: "Intervalos 5x1000m")
        description: Breve descripcion del objetivo (ej: "Trabajo de VO2max")
        pre_activity_comments: Estructura DETALLADA para el atleta incluyendo:
                               - Calentamiento
                               - Serie principal
                               - Enfriamiento
                               - Notas sobre intensidad/terreno/respiracion
        planned_values: OBLIGATORIO. Dict con valores numericos. SIEMPRE incluir:
                        - "Duration" (formato h:m:s): OBLIGATORIO
                        - "Distance" (formato numero): RECOMENDADO
                        - "TSS" (formato numero): RECOMENDADO
                        - "IF" (formato decimal): RECOMENDADO
                        Otros: Average Pace, Elevation Gain, Calories, Work
                        Ej: {"Duration": "1:00:00", "Distance": "10", "TSS": "75", "IF": "0.85"}
        folder_name: Carpeta destino. Default: "Neuronomy"
        click_save: Si True, guarda el workout automaticamente. Default: True
        
    Parametros disponibles por tipo (consulta obtener_esquema_parametros_workout):
        - Run: Duration, Distance, Average Pace, Elevation Gain, Calories, TSS, IF, Work
        - Bike: Duration, Distance, Average Speed, Elevation Gain, Calories, TSS, IF, Work
        - Swim: Duration, Distance, Average Pace, Calories, TSS, IF
        - Strength: Duration, Calories, TSS, IF
        
    Returns:
        Mensaje indicando exito o error
        
    Ejemplo correcto de uso:
        crear_workout(
            workout_type="Run",
            title="Rodaje + Técnica + Strides",
            description="Base aeróbica y técnica de carrera",
            pre_activity_comments='''Estructura:
- Calentamiento: 10-15 min Z1-Z2
- Técnica: 6-8 min drills (skipping, talones, zancadas)
- Strides: 4-6 x 20s rápidos con recuperación
- Rodaje: 25-35 min Z2 constante
- Enfriamiento: 5-10 min muy suave

Intensidad: Mantén Z2 en bloque central (~70-78% FCmax)
Terreno: Preferentemente llano o poco desnivel
Respiración: Nasal en Z2 si es posible''',
            planned_values={
                "Duration": "1:00:00",
                "Distance": "10",
                "TSS": "55",
                "IF": "0.75",
                "Elevation Gain": "50",
                "Calories": "500"
            },
            folder_name="Neuronomy"
        )
    """
    try:
        result = create_workout(
            folder_name=folder_name,
            workout_type=workout_type,
            title=title,
            description=description,
            pre_activity_comments=pre_activity_comments,
            planned_values=planned_values,
            click_save=click_save
        )
        return result
    except Exception as e:
        return f"[ERROR] Error al crear workout: {str(e)}"


# ----------------------------------------------------------------------------
# HERRAMIENTAS MCP PARA CALENDARIO
# ----------------------------------------------------------------------------

@mcp.tool()
def navegar_calendario(accion: str) -> str:
    """
    Navega por el calendario.
    
    Args:
        accion: Accion a realizar ("adelante", "atras", "hoy")
        
    Returns:
        Mensaje de confirmacion o error
    """
    try:
        accion_lower = accion.lower()
        
        if accion_lower in ["adelante", "forward", "siguiente"]:
            week_forward()
            return "[OK] Avanzado una semana"
        elif accion_lower in ["atras", "backward", "anterior"]:
            week_backward()
            return "[OK] Retrocedido una semana"
        elif accion_lower in ["hoy", "today"]:
            calendar_go_to_today()
            return "[OK] Navegado a la semana actual"
        else:
            return f"[ERROR] Accion '{accion}' no reconocida. Usa: 'adelante', 'atras' o 'hoy'"
    except Exception as e:
        return f"[ERROR] Error al navegar: {str(e)}"


@mcp.tool()
def clickear_fecha_calendario(fecha: str) -> str:
    """
    Navega a una fecha especifica en el calendario y hace clic en ella.
    Usa navegacion avanzada con reintentos automaticos.
    
    Args:
        fecha: Fecha en formato YYYY-MM-DD
        
    Returns:
        Mensaje de confirmacion o error
    """
    try:
        click_calendar_date_until(fecha, use_today=True)
        return f"[OK] Navegado y clickeado en la fecha {fecha}"
    except Exception as e:
        return f"[ERROR] Error al navegar a la fecha: {str(e)}"


@mcp.tool()
def obtener_datos_calendario(fecha: str, limit: int = None) -> Dict[str, Any]:
    """
    Obtiene todos los workouts en el calendario en una fecha especifica.
    
    Args:
        fecha: Fecha en formato YYYY-MM-DD
        limit: Si se proporciona, limita el numero de workouts a obtener
        
    Returns:
        Dict con todos los workouts en el calendario
    """
    try:
        workouts = get_all_quickviews_on_date(fecha, limit=limit)
        return workouts if workouts else {"error": "No se pudieron obtener los workouts"}
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


@mcp.tool()
def verificar_driver() -> Dict[str, Any]:
    """
    Verifica el estado del driver de Selenium.
    Util para diagnosticar problemas de conexion.
    
    Returns:
        Dict con informacion del estado del driver
    """
    try:
        if not is_driver_ready():
            return {
                "driver_activo": False,
                "mensaje": "[ERROR] No hay driver configurado. Usa inicializar_con_driver() primero."
            }
        
        driver = get_driver()
        url_actual = driver.current_url
        
        return {
            "driver_activo": True,
            "url_actual": url_actual,
            "mensaje": "[OK] Driver activo y funcionando"
        }
    except Exception as e:
        return {
            "driver_activo": False,
            "error": f"Error: {str(e)}"
        }


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    # El driver debe ser inyectado antes de ejecutar el servidor
    # Ejemplo de uso:
    #
    # from selenium import webdriver
    # driver = webdriver.Chrome()
    # driver.get('https://app.trainingpeaks.com')
    # # ... preparar sesion ...
    # inicializar_con_driver(driver)
    # mcp.run()
    
    if not is_driver_ready():
        print("ADVERTENCIA: No hay driver configurado.")
        print("Usa inicializar_con_driver(driver) antes de ejecutar el servidor.")
        print("El servidor iniciara pero las funciones fallaran sin un driver activo.")
    
    mcp.run()
