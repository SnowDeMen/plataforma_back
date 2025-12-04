"""
MCP Tools Adapter - Expone las herramientas del MCP en formato OpenAI.

Este adaptador se conecta al servidor MCP de TrainingPeaks (via MCPServerManager)
y expone las herramientas como funciones compatibles con OpenAI function calling.
"""
import json
from typing import List, Dict, Any, Optional
from loguru import logger

from app.shared.utils.audit_logger import AuditLogger
from .mcp_server_manager import MCPServerManager


class MCPToolsAdapter:
    """
    Adaptador que expone las herramientas del servidor MCP como funciones
    compatibles con OpenAI function calling.
    
    Se conecta al MCPServerManager que ejecuta el servidor MCP de TrainingPeaks.
    
    Uso:
        # Obtener herramientas para OpenAI
        tools = MCPToolsAdapter.get_openai_tools()
        
        # Ejecutar una herramienta (via servidor MCP)
        result = MCPToolsAdapter.execute_tool("crear_workout", {...})
    """
    
    # Definicion de herramientas en formato OpenAI
    TOOLS_DEFINITION: List[Dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "obtener_datos_calendario",
                "description": "Obtiene todos los workouts de una fecha especifica en el calendario de TrainingPeaks. Retorna informacion detallada de cada workout incluyendo titulo, tipo, duracion, metricas, descripcion, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha": {
                            "type": "string",
                            "description": "Fecha en formato YYYY-MM-DD"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Limite de workouts a obtener. Si no se proporciona, obtiene todos."
                        }
                    },
                    "required": ["fecha"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "navegar_calendario",
                "description": "Navega por el calendario de TrainingPeaks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "accion": {
                            "type": "string",
                            "enum": ["adelante", "atras", "hoy"],
                            "description": "Accion de navegacion: 'adelante' (siguiente semana), 'atras' (semana anterior), 'hoy' (semana actual)"
                        }
                    },
                    "required": ["accion"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "clickear_fecha_calendario",
                "description": "Navega a una fecha especifica en el calendario y hace clic en ella.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha": {
                            "type": "string",
                            "description": "Fecha en formato YYYY-MM-DD"
                        }
                    },
                    "required": ["fecha"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "listar_workouts",
                "description": "Lista todos los workouts disponibles en una Workout Library especifica.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_library": {
                            "type": "string",
                            "description": "Nombre (o parte del nombre) de la library a listar"
                        },
                        "exact": {
                            "type": "boolean",
                            "description": "Si True, busca match exacto del nombre. Default: False"
                        }
                    },
                    "required": ["nombre_library"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "obtener_datos_workout",
                "description": "Obtiene todos los datos detallados de un workout de la library (metricas, descripcion, estructura, etc).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_workout": {
                            "type": "string",
                            "description": "Nombre del workout"
                        },
                        "nombre_library": {
                            "type": "string",
                            "description": "Nombre de la library donde esta el workout"
                        }
                    },
                    "required": ["nombre_workout", "nombre_library"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "arrastrar_workout_a_calendario",
                "description": "Arrastra un workout de la library al calendario en una fecha especifica.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nombre_workout": {
                            "type": "string",
                            "description": "Nombre del workout a arrastrar"
                        },
                        "fecha_destino": {
                            "type": "string",
                            "description": "Fecha destino en formato YYYY-MM-DD"
                        },
                        "nombre_library": {
                            "type": "string",
                            "description": "Nombre de la library donde esta el workout (opcional)"
                        }
                    },
                    "required": ["nombre_workout", "fecha_destino"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "verificar_driver",
                "description": "Verifica el estado del driver de Selenium. Util para diagnosticar problemas de conexion con TrainingPeaks.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "obtener_estado_paneles",
                "description": "Obtiene el estado actual del panel de Workout Library (si esta abierto o cerrado).",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "obtener_esquema_parametros_workout",
                "description": "Obtiene el esquema de parametros disponibles para crear workouts segun el tipo. IMPORTANTE: Consulta esta herramienta ANTES de crear un workout.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workout_type": {
                            "type": "string",
                            "description": "Tipo de workout (Run, Bike, Swim, etc.) o None para ver todos"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "crear_workout",
                "description": "Crea un workout directamente en TrainingPeaks dentro de la Workout Library. CRITICO: SIEMPRE incluir planned_values con Duration, Distance, TSS e IF. Sin planned_values los campos numericos quedan vacios en TrainingPeaks. Consulta obtener_esquema_parametros_workout() ANTES de usar esta herramienta.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workout_type": {
                            "type": "string",
                            "description": "Tipo de workout: Run, Bike, Swim, Strength, Walk, Rowing, Mtn Bike, XC-Ski, Brick, Crosstrain, Custom, Other, Day off",
                            "default": "Run"
                        },
                        "title": {
                            "type": "string",
                            "description": "Titulo conciso del workout. Ej: 'Intervalos 5x1000m', 'Rodaje Base', 'Tempo 20min'"
                        },
                        "description": {
                            "type": "string",
                            "description": "Breve descripcion del objetivo (1-2 lineas). Ej: 'Trabajo de VO2max con recuperaciones activas'"
                        },
                        "pre_activity_comments": {
                            "type": "string",
                            "description": "Instrucciones detalladas que vera el atleta ANTES de entrenar. Incluye estructura completa: calentamiento, serie principal, enfriamiento. Puedes usar saltos de linea."
                        },
                        "planned_values": {
                            "type": "object",
                            "description": "OBLIGATORIO. Diccionario con valores numericos que rellenaran TrainingPeaks. Formato: {\"Duration\": \"h:m:s\", \"Distance\": \"km\", \"TSS\": \"numero\", \"IF\": \"decimal\", etc}. Ej: {\"Duration\": \"1:00:00\", \"Distance\": \"10\", \"TSS\": \"75\", \"IF\": \"0.85\"}. SIEMPRE incluir Duration + Distance o TSS."
                        },
                        "folder_name": {
                            "type": "string",
                            "description": "Carpeta destino dentro de la Workout Library. Default: 'Neuronomy'"
                        },
                        "click_save": {
                            "type": "boolean",
                            "description": "Si True, guarda el workout automaticamente. Default: True",
                            "default": True
                        }
                    },
                    "required": ["title", "workout_type", "planned_values"]
                }
            }
        }
    ]
    
    @classmethod
    def get_openai_tools(cls) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de herramientas en formato OpenAI.
        
        Returns:
            Lista de herramientas para el parametro 'tools' de OpenAI
        """
        return cls.TOOLS_DEFINITION
    
    @classmethod
    def execute_tool(
        cls,
        tool_name: str,
        arguments: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> str:
        """
        Ejecuta una herramienta del servidor MCP.
        
        Llama al MCPServerManager que a su vez ejecuta la funcion
        decorada con @mcp.tool() del servidor MCP de TrainingPeaks.
        
        Args:
            tool_name: Nombre de la herramienta a ejecutar
            arguments: Argumentos para la herramienta
            session_id: ID de sesion para logging
            
        Returns:
            Resultado de la herramienta como string JSON
        """
        # Verificar que el servidor MCP este listo
        if not MCPServerManager.is_running():
            error_result = {
                "error": "Servidor MCP no inicializado. Las herramientas no estan disponibles.",
                "sugerencia": "Verifica que la sesion de entrenamiento este activa."
            }
            return json.dumps(error_result, ensure_ascii=False)
        
        # Verificar que la herramienta existe
        tool_names = [t["function"]["name"] for t in cls.TOOLS_DEFINITION]
        if tool_name not in tool_names:
            error_result = {"error": f"Herramienta '{tool_name}' no encontrada"}
            return json.dumps(error_result, ensure_ascii=False)
        
        # Validar planned_values para crear_workout
        if tool_name == "crear_workout":
            if "planned_values" not in arguments or not arguments["planned_values"]:
                error_result = {
                    "error": True,
                    "message": "ERROR: planned_values es OBLIGATORIO. Debes incluir un diccionario con al menos Duration y TSS/Distance. Ejemplo: {'Duration': '1:00:00', 'Distance': '10', 'TSS': '55'}. Reintenta la llamada con planned_values completo."
                }
                logger.warning(f"MCPToolsAdapter: crear_workout rechazado - falta planned_values")
                return json.dumps(error_result, ensure_ascii=False)
        
        # Log de la llamada
        if session_id:
            AuditLogger.log_mcp_call(
                session_id=session_id,
                action=f"MCP_TOOL_{tool_name.upper()}",
                details={"arguments": arguments},
                success=True
            )
        
        logger.info(f"MCPToolsAdapter: Ejecutando MCP tool '{tool_name}' con args: {arguments}")
        
        try:
            # Llamar a la herramienta via MCPServerManager
            result = MCPServerManager.call_tool(tool_name, arguments)
            
            # Convertir resultado a JSON string
            if isinstance(result, dict):
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
            elif isinstance(result, str):
                result_str = result
            else:
                result_str = str(result)
            
            logger.info(f"MCPToolsAdapter: MCP tool '{tool_name}' completado")
            
            # Log del resultado
            if session_id:
                AuditLogger.log_mcp_call(
                    session_id=session_id,
                    action=f"MCP_TOOL_{tool_name.upper()}_RESULT",
                    details={"result_length": len(result_str)},
                    success=True
                )
            
            return result_str
            
        except Exception as e:
            error_msg = f"Error ejecutando MCP tool {tool_name}: {str(e)}"
            logger.error(f"MCPToolsAdapter: {error_msg}")
            
            # Log del error
            if session_id:
                AuditLogger.log_mcp_call(
                    session_id=session_id,
                    action=f"MCP_TOOL_{tool_name.upper()}_ERROR",
                    details={"error": str(e)},
                    success=False,
                    error=str(e)
                )
            
            return json.dumps({"error": error_msg}, ensure_ascii=False)
    
    @classmethod
    def get_tool_names(cls) -> List[str]:
        """Obtiene la lista de nombres de herramientas disponibles."""
        return [tool["function"]["name"] for tool in cls.TOOLS_DEFINITION]
    
    @classmethod
    def is_available(cls) -> bool:
        """
        Verifica si el adaptador esta disponible.
        
        Requiere que el MCPServerManager este inicializado con un driver activo.
        """
        return MCPServerManager.is_running()
    
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        Obtiene el estado detallado del adaptador y servidor MCP.
        
        Returns:
            Dict con informacion del estado
        """
        mcp_status = MCPServerManager.get_status()
        
        return {
            "adapter_available": cls.is_available(),
            "tools_defined": len(cls.TOOLS_DEFINITION),
            "mcp_server": mcp_status
        }
