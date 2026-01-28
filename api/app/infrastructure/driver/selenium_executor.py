"""
Ejecutor de operaciones de Selenium en threads separados.

Este modulo proporciona utilidades para ejecutar funciones de Selenium
en threads del ThreadPoolExecutor, evitando bloquear el event loop de asyncio.
Esto permite que el servidor FastAPI/uvicorn siga atendiendo requests
(como healthchecks) mientras Selenium ejecuta operaciones largas.

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
from typing import TypeVar, Callable, Any
from functools import partial

from loguru import logger


T = TypeVar("T")


async def run_selenium(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Ejecuta una funcion de Selenium en un thread separado del ThreadPoolExecutor.
    
    Permite que operaciones bloqueantes de Selenium (driver.get, wait.until, etc.)
    se ejecuten sin bloquear el event loop de asyncio, manteniendo el servidor
    responsivo para otras requests.
    
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
    
    try:
        return await asyncio.to_thread(func, *args)
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
    
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(func, *args),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.error(f"Timeout ({timeout_seconds}s) en operacion Selenium: {func}")
        raise
    except Exception as e:
        logger.error(f"Error en operacion Selenium (thread): {type(e).__name__}: {e}")
        raise
