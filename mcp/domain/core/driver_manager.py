"""
Driver Manager - Gestión centralizada del WebDriver de Selenium

Este módulo permite inyectar un driver externo ya inicializado,
evitando la necesidad de crear sesiones desde cero.
"""

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from typing import Optional

# Variables globales para el driver y wait
_driver: Optional[webdriver.Chrome] = None
_wait: Optional[WebDriverWait] = None


def set_driver(driver: webdriver.Chrome, wait: WebDriverWait = None, default_timeout: int = 10):
    """
    Inyecta un driver externo ya inicializado.
    
    Permite conectar el sistema a un driver de Selenium que ya existe
    y está listo para usarse (con sesión activa, página cargada, etc).
    
    Args:
        driver: Instancia de WebDriver ya inicializada
        wait: WebDriverWait ya configurado (opcional, se crea uno si no se proporciona)
        default_timeout: Timeout por defecto para crear el WebDriverWait si no se proporciona
        
    Raises:
        ValueError: Si el driver es None o no es válido
    """
    global _driver, _wait
    
    if driver is None:
        raise ValueError("El driver no puede ser None")
    
    # Verificar que el driver está activo
    try:
        _ = driver.current_url
    except Exception as e:
        raise ValueError(f"El driver proporcionado no está activo o es inválido: {e}")
    
    _driver = driver
    _wait = wait if wait is not None else WebDriverWait(driver, default_timeout)


def is_driver_ready() -> bool:
    """
    Verifica si hay un driver configurado y listo para usar.
    
    Returns:
        True si el driver está configurado y activo, False en caso contrario
    """
    global _driver
    
    if _driver is None:
        return False
    
    try:
        _ = _driver.current_url
        return True
    except Exception:
        return False


def ensure_driver():
    """
    Verifica que el driver esté configurado y en buen estado.
    
    A diferencia de la versión anterior, esta función NO inicializa
    un driver automáticamente. El driver debe ser inyectado previamente
    con set_driver().
    
    Raises:
        RuntimeError: Si no hay driver configurado o está en mal estado
    """
    global _driver, _wait
    
    if _driver is None:
        raise RuntimeError(
            "No hay driver configurado. Usa set_driver() para inyectar "
            "un driver de Selenium antes de usar las funciones del MCP."
        )
    
    # Verificar que el driver sigue siendo válido
    try:
        _ = _driver.current_url
    except Exception as e:
        _driver = None
        _wait = None
        raise RuntimeError(
            f"El driver configurado ya no es válido: {e}. "
            "Inyecta un nuevo driver con set_driver()."
        )


def get_driver() -> webdriver.Chrome:
    """
    Obtiene el driver de Selenium configurado.
    
    Returns:
        WebDriver de Chrome
        
    Raises:
        RuntimeError: Si no hay driver configurado
    """
    ensure_driver()
    return _driver


def get_wait() -> WebDriverWait:
    """
    Obtiene el objeto WebDriverWait configurado.
    
    Returns:
        WebDriverWait configurado
        
    Raises:
        RuntimeError: Si no hay driver configurado
    """
    ensure_driver()
    return _wait


def clear_driver():
    """
    Limpia las referencias al driver sin cerrarlo.
    
    Útil cuando el driver será gestionado externamente y solo
    queremos desconectar este módulo del driver.
    """
    global _driver, _wait
    _driver = None
    _wait = None
