"""
Ejecutor de operaciones de Selenium en threads separados.

Este modulo proporciona utilidades para ejecutar funciones de Selenium
en un ThreadPoolExecutor dedicado, evitando bloquear el event loop de asyncio.
Esto permite que el servidor FastAPI/uvicorn siga atendiendo requests
(como healthchecks) mientras Selenium ejecuta operaciones largas.

Caracteristicas:
- ThreadPoolExecutor dedicado con limite explicito de workers (default: 8)
- Semaforo global para limitar operaciones concurrentes de Selenium
- Evita saturar el executor por defecto del event loop
- Threads con nombre prefijado para facil identificacion en logs/debugging

Uso:
    from app.infrastructure.driver.selenium_executor import run_selenium
    
    # Ejecutar funcion sincrona en thread
    result = await run_selenium(driver.get, "https://example.com")
    
    # Ejecutar metodo de servicio
    await run_selenium(auth_service.login_with_cookie)
    
    # Con argumentos
    await run_selenium(athlete_service.select_athlete, athlete_name)
"""
import asyncio
import atexit
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar, Callable, Any
from functools import partial

from loguru import logger


T = TypeVar("T")

# Configuracion del ThreadPool dedicado para Selenium
SELENIUM_MAX_WORKERS = 8

# Limite maximo de operaciones de Selenium concurrentes en todo el sistema.
# Esto actua como una capa adicional de proteccion sobre el ThreadPoolExecutor,
# evitando que demasiadas sesiones saturen el sistema simultaneamente.
SELENIUM_MAX_CONCURRENT_OPS = 8

# ThreadPoolExecutor dedicado para operaciones de Selenium.
# Usar un executor separado evita competir con el executor por defecto
# del event loop, que puede ser usado por otras operaciones async.
_selenium_executor = ThreadPoolExecutor(
    max_workers=SELENIUM_MAX_WORKERS,
    thread_name_prefix="selenium-"
)

# Semaforo global para limitar operaciones de Selenium concurrentes.
# Previene que multiples sesiones saturen el sistema con operaciones
# de Selenium simultaneas. Esto es especialmente util cuando hay muchos
# atletas activos al mismo tiempo.
_global_semaphore: asyncio.Semaphore | None = None


def _get_global_semaphore() -> asyncio.Semaphore:
    """
    Obtiene el semaforo global, creandolo si es necesario.
    
    El semaforo se crea lazy porque asyncio.Semaphore debe crearse
    dentro de un contexto con event loop activo.
    """
    global _global_semaphore
    if _global_semaphore is None:
        _global_semaphore = asyncio.Semaphore(SELENIUM_MAX_CONCURRENT_OPS)
        logger.debug(
            f"Semaforo global de Selenium creado "
            f"(max_concurrent: {SELENIUM_MAX_CONCURRENT_OPS})"
        )
    return _global_semaphore


def _shutdown_executor() -> None:
    """Cierra el executor de Selenium al terminar la aplicacion."""
    logger.info("Cerrando ThreadPoolExecutor de Selenium...")
    _selenium_executor.shutdown(wait=True)
    logger.info("ThreadPoolExecutor de Selenium cerrado")


# Registrar cleanup al terminar la aplicacion
atexit.register(_shutdown_executor)


async def run_selenium(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Ejecuta una funcion de Selenium en un thread del ThreadPoolExecutor dedicado.
    
    Permite que operaciones bloqueantes de Selenium (driver.get, wait.until, etc.)
    se ejecuten sin bloquear el event loop de asyncio, manteniendo el servidor
    responsivo para otras requests.
    
    Caracteristicas:
    - Usa un ThreadPoolExecutor dedicado con limite de workers explicito
    - Limita operaciones concurrentes via semaforo global
    - Evita saturar el executor por defecto del event loop
    
    Args:
        func: Funcion o metodo sincrono a ejecutar
        *args: Argumentos posicionales para la funcion
        **kwargs: Argumentos con nombre para la funcion
        
    Returns:
        El resultado de la funcion ejecutada
        
    Raises:
        Cualquier excepcion que la funcion original lance
        
    Ejemplo:
        # Crear driver en thread
        driver, wait = await run_selenium(create_driver)
        
        # Login en thread
        await run_selenium(auth_service.login_with_cookie)
        
        # Navegacion en thread
        await run_selenium(driver.get, "https://app.trainingpeaks.com")
    """
    if kwargs:
        # Usar partial para incluir kwargs
        func = partial(func, **kwargs)
    
    loop = asyncio.get_running_loop()
    semaphore = _get_global_semaphore()
    
    # Adquirir semaforo para limitar concurrencia global
    async with semaphore:
        try:
            return await loop.run_in_executor(_selenium_executor, func, *args)
        except Exception as e:
            logger.error(f"Error en operacion Selenium (thread): {type(e).__name__}: {e}")
            raise


async def run_selenium_with_timeout(
    func: Callable[..., T],
    *args: Any,
    timeout_seconds: float = 60.0,
    **kwargs: Any
) -> T:
    """
    Ejecuta una funcion de Selenium con timeout adicional a nivel asyncio.
    
    Util para operaciones que pueden colgarse indefinidamente.
    El timeout de Selenium (WebDriverWait) sigue aplicando internamente,
    pero este timeout proporciona una capa adicional de proteccion.
    
    Caracteristicas:
    - Usa el ThreadPoolExecutor dedicado para Selenium
    - Limita operaciones concurrentes via semaforo global
    - Timeout adicional a nivel asyncio
    
    Args:
        func: Funcion o metodo sincrono a ejecutar
        *args: Argumentos posicionales
        timeout_seconds: Timeout maximo en segundos (default: 60)
        **kwargs: Argumentos con nombre
        
    Returns:
        El resultado de la funcion ejecutada
        
    Raises:
        asyncio.TimeoutError: Si la operacion excede el timeout
        Cualquier excepcion que la funcion original lance
    """
    if kwargs:
        func = partial(func, **kwargs)
    
    loop = asyncio.get_running_loop()
    semaphore = _get_global_semaphore()
    
    # Adquirir semaforo para limitar concurrencia global
    async with semaphore:
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(_selenium_executor, func, *args),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout ({timeout_seconds}s) en operacion Selenium: {func}")
            raise
        except Exception as e:
            logger.error(f"Error en operacion Selenium (thread): {type(e).__name__}: {e}")
            raise


def get_executor_stats() -> dict:
    """
    Retorna estadisticas del ThreadPoolExecutor y semaforo de Selenium.
    
    Util para monitoreo y debugging.
    
    Returns:
        Dict con max_workers, max_concurrent_ops, y estado del executor
    """
    semaphore = _global_semaphore
    semaphore_info = {
        "max_concurrent_ops": SELENIUM_MAX_CONCURRENT_OPS,
        "available_slots": semaphore._value if semaphore else SELENIUM_MAX_CONCURRENT_OPS
    }
    
    return {
        "thread_pool": {
            "max_workers": SELENIUM_MAX_WORKERS,
            "thread_name_prefix": "selenium-",
            "shutdown": _selenium_executor._shutdown if hasattr(_selenium_executor, '_shutdown') else None
        },
        "semaphore": semaphore_info
    }
