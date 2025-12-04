"""
MCPServerManager - Gestor del servidor MCP ejecutado en background.

Inicia el servidor MCP de TrainingPeaks en un thread separado y proporciona
un cliente MCP para comunicarse con el. El driver de Selenium se inyecta
directamente ya que comparten el mismo proceso.
"""
import sys
import asyncio
import threading
from typing import Optional, Dict, Any, List
from pathlib import Path
from contextlib import asynccontextmanager

from loguru import logger

def _find_mcp_path() -> Path:
    """
    Busca el path del modulo MCP de forma robusta.
    Funciona tanto en desarrollo local como en Docker.
    """
    current = Path(__file__).parent
    # Buscar hacia arriba hasta encontrar la carpeta mcp/ con el archivo principal
    for _ in range(6):
        current = current.parent
        mcp_candidate = current / "mcp"
        if mcp_candidate.exists() and (mcp_candidate / "trainingpeaks_mcp_server_modular.py").exists():
            return mcp_candidate
    # Fallback: path absoluto para Docker (/app/mcp)
    docker_path = Path("/app/mcp")
    if docker_path.exists():
        return docker_path
    # Ultimo fallback: path relativo original
    return Path(__file__).parent.parent.parent.parent.parent / "mcp"

# Ruta al modulo MCP (detectada automaticamente)
MCP_MODULE_PATH = _find_mcp_path()


class MCPServerManager:
    """
    Gestor del servidor MCP que corre en background.
    
    Ejecuta el servidor MCP en un thread separado e inyecta el driver
    de Selenium para que las herramientas puedan interactuar con TrainingPeaks.
    
    Uso:
        # Iniciar servidor con driver
        await MCPServerManager.start(driver, wait, session_id)
        
        # Llamar herramienta via cliente MCP
        result = await MCPServerManager.call_tool("crear_workout", {...})
        
        # Detener servidor
        await MCPServerManager.stop()
    """
    
    # Estado del servidor
    _server_thread: Optional[threading.Thread] = None
    _server_running: bool = False
    _current_session_id: Optional[str] = None
    _event_loop: Optional[asyncio.AbstractEventLoop] = None
    _mcp_instance = None
    _driver_ready: bool = False
    
    # Cache de herramientas disponibles
    _available_tools: Dict[str, Any] = {}
    
    @classmethod
    def _ensure_mcp_path(cls) -> bool:
        """Agrega el path del modulo MCP al sys.path si no esta."""
        mcp_path_str = str(MCP_MODULE_PATH)
        
        if not MCP_MODULE_PATH.exists():
            logger.error(f"MCPServerManager: Path del MCP no existe: {mcp_path_str}")
            return False
        
        if mcp_path_str not in sys.path:
            sys.path.insert(0, mcp_path_str)
            logger.debug(f"MCPServerManager: Path agregado: {mcp_path_str}")
        
        return True
    
    @classmethod
    def start(
        cls,
        driver,
        wait,
        session_id: str,
        run_server: bool = False
    ) -> bool:
        """
        Inicializa el MCP con el driver e inicia el servidor en background.
        
        Args:
            driver: WebDriver de Selenium con sesion activa
            wait: WebDriverWait configurado
            session_id: ID de la sesion
            run_server: Si True, ejecuta el servidor MCP en background (para uso con cliente)
            
        Returns:
            True si se inicio correctamente
        """
        if cls._server_running:
            logger.warning("MCPServerManager: El servidor ya esta en ejecucion")
            return True
        
        try:
            # Agregar path del MCP
            if not cls._ensure_mcp_path():
                return False
            
            # Importar e inyectar el driver al modulo MCP
            from domain.core import set_driver, is_driver_ready
            set_driver(driver, wait)
            
            if not is_driver_ready():
                logger.error("MCPServerManager: El driver no se configuro correctamente")
                return False
            
            cls._driver_ready = True
            cls._current_session_id = session_id
            
            # Cargar referencia al modulo MCP
            from trainingpeaks_mcp_server_modular import mcp
            cls._mcp_instance = mcp
            
            # Cargar herramientas disponibles
            cls._load_available_tools()
            
            logger.info(f"MCPServerManager: Inicializado para sesion {session_id}")
            logger.info(f"MCPServerManager: {len(cls._available_tools)} herramientas disponibles")
            
            # Opcionalmente ejecutar servidor en background
            if run_server:
                cls._start_server_thread()
            
            return True
            
        except ImportError as e:
            logger.error(f"MCPServerManager: Error al importar modulos: {e}")
            return False
        except Exception as e:
            logger.error(f"MCPServerManager: Error durante inicio: {e}")
            return False
    
    @classmethod
    def _load_available_tools(cls) -> None:
        """Carga las herramientas disponibles del servidor MCP."""
        try:
            from trainingpeaks_mcp_server_modular import (
                obtener_datos_calendario,
                navegar_calendario,
                clickear_fecha_calendario,
                listar_workouts,
                obtener_datos_workout,
                arrastrar_workout_a_calendario,
                verificar_driver,
                obtener_estado_paneles,
                crear_workout,
                obtener_esquema_parametros_workout
            )
            
            # Registrar las funciones decoradas con @mcp.tool()
            cls._available_tools = {
                "obtener_datos_calendario": obtener_datos_calendario,
                "navegar_calendario": navegar_calendario,
                "clickear_fecha_calendario": clickear_fecha_calendario,
                "listar_workouts": listar_workouts,
                "obtener_datos_workout": obtener_datos_workout,
                "arrastrar_workout_a_calendario": arrastrar_workout_a_calendario,
                "verificar_driver": verificar_driver,
                "obtener_estado_paneles": obtener_estado_paneles,
                "crear_workout": crear_workout,
                "obtener_esquema_parametros_workout": obtener_esquema_parametros_workout
            }
            
            logger.info(f"MCPServerManager: Herramientas cargadas: {list(cls._available_tools.keys())}")
            
        except ImportError as e:
            logger.error(f"MCPServerManager: Error al cargar herramientas: {e}")
            cls._available_tools = {}
    
    @classmethod
    def _start_server_thread(cls) -> None:
        """Inicia el servidor MCP en un thread de background."""
        if cls._server_running:
            return
        
        def run_mcp_server():
            """Ejecuta el servidor MCP en el thread."""
            try:
                cls._server_running = True
                cls._event_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(cls._event_loop)
                
                logger.info("MCPServerManager: Servidor MCP iniciando en background...")
                cls._mcp_instance.run()
                
            except Exception as e:
                logger.error(f"MCPServerManager: Error en servidor: {e}")
            finally:
                cls._server_running = False
                if cls._event_loop:
                    cls._event_loop.close()
        
        cls._server_thread = threading.Thread(target=run_mcp_server, daemon=True)
        cls._server_thread.start()
        logger.info("MCPServerManager: Thread del servidor iniciado")
    
    @classmethod
    def call_tool(cls, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Llama a una herramienta del MCP directamente.
        
        Esta es la forma principal de ejecutar herramientas MCP.
        Llama directamente a la funcion decorada con @mcp.tool().
        
        Args:
            tool_name: Nombre de la herramienta a ejecutar
            arguments: Argumentos para la herramienta
            
        Returns:
            Resultado de la herramienta
        """
        if not cls._driver_ready:
            return {"error": "MCP no inicializado. Llama start() primero."}
        
        if tool_name not in cls._available_tools:
            return {"error": f"Herramienta '{tool_name}' no encontrada"}
        
        try:
            func = cls._available_tools[tool_name]
            args = arguments or {}
            
            logger.info(f"MCPServerManager: Ejecutando {tool_name}")
            result = func(**args)
            
            logger.info(f"MCPServerManager: {tool_name} completado")
            return result
            
        except Exception as e:
            logger.error(f"MCPServerManager: Error ejecutando {tool_name}: {e}")
            return {"error": f"Error: {str(e)}"}
    
    @classmethod
    def stop(cls) -> bool:
        """
        Detiene el servidor MCP y limpia los recursos.
        
        Returns:
            True si se detuvo correctamente
        """
        try:
            # Limpiar referencia al driver
            if cls._driver_ready:
                from domain.core import clear_driver
                clear_driver()
            
            cls._driver_ready = False
            cls._server_running = False
            cls._current_session_id = None
            cls._available_tools = {}
            cls._mcp_instance = None
            
            logger.info("MCPServerManager: Servidor detenido")
            return True
            
        except Exception as e:
            logger.error(f"MCPServerManager: Error al detener: {e}")
            return False
    
    @classmethod
    def is_running(cls) -> bool:
        """Verifica si el MCP esta listo para recibir comandos."""
        return cls._driver_ready
    
    @classmethod
    def get_current_session_id(cls) -> Optional[str]:
        """Obtiene el ID de la sesion actualmente conectada."""
        return cls._current_session_id
    
    @classmethod
    def get_available_tools(cls) -> List[str]:
        """Obtiene la lista de herramientas disponibles."""
        return list(cls._available_tools.keys())
    
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Obtiene el estado actual del servidor MCP."""
        return {
            "initialized": cls._driver_ready,
            "server_running": cls._server_running,
            "session_id": cls._current_session_id,
            "tools_count": len(cls._available_tools),
            "mcp_path": str(MCP_MODULE_PATH),
            "mcp_path_exists": MCP_MODULE_PATH.exists()
        }

