"""
Lock de Selenium por sesion.

Motivacion:
- El driver de Selenium NO es seguro para uso concurrente.
- En este proyecto, varias rutas (chat/MCP/historial) pueden intentar usar
  el mismo driver asociado a `session_id`.
- Necesitamos serializar el acceso sin introducir dependencias externas.

Caracteristicas:
- Lock por session_id para serializar operaciones de Selenium
- Timeout configurable para evitar deadlocks (default: 60 segundos)
- Limpieza de locks de sesiones cerradas
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from loguru import logger


# Timeout por defecto para adquirir un lock (en segundos)
DEFAULT_LOCK_TIMEOUT = 60.0


class SeleniumLockTimeoutError(Exception):
    """Excepcion lanzada cuando no se puede adquirir el lock dentro del timeout."""
    
    def __init__(self, session_id: str, timeout: float):
        self.session_id = session_id
        self.timeout = timeout
        super().__init__(
            f"Timeout ({timeout}s) adquiriendo lock de Selenium para sesion: {session_id}"
        )


class SeleniumSessionLockManager:
    """
    Gestor de locks por `session_id`.

    Implementacion:
    - Usa `threading.Lock` por compatibilidad con codigo sincrono.
    - La adquisicion se ejecuta en un thread via `asyncio.to_thread` para
      no bloquear el event loop.
    - Timeout configurable para evitar deadlocks.
    """

    _locks: Dict[str, threading.Lock] = {}
    _meta_lock = threading.Lock()

    @classmethod
    def _get_or_create_lock(cls, session_id: str) -> threading.Lock:
        """Obtiene o crea un lock para la sesion especificada."""
        with cls._meta_lock:
            lock = cls._locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                cls._locks[session_id] = lock
            return lock

    @classmethod
    @asynccontextmanager
    async def lock(
        cls, 
        session_id: str, 
        timeout: float = DEFAULT_LOCK_TIMEOUT
    ) -> AsyncIterator[None]:
        """
        Context manager async para adquirir el lock de una sesion.
        
        Args:
            session_id: ID de la sesion para la cual adquirir el lock
            timeout: Tiempo maximo de espera para adquirir el lock (segundos).
                     Si es None o <= 0, espera indefinidamente (no recomendado).
                     Default: 60 segundos.
                     
        Yields:
            None - Permite ejecutar codigo mientras se tiene el lock
            
        Raises:
            SeleniumLockTimeoutError: Si no se puede adquirir el lock
                dentro del timeout especificado.
                
        Ejemplo:
            async with SeleniumSessionLockManager.lock(session_id):
                # Operaciones de Selenium serializadas
                await run_selenium(driver.get, url)
        """
        lock = cls._get_or_create_lock(session_id)
        
        # Intentar adquirir el lock con timeout
        if timeout and timeout > 0:
            acquired = await asyncio.to_thread(lock.acquire, timeout=timeout)
            if not acquired:
                logger.warning(
                    f"Timeout adquiriendo lock para sesion {session_id} "
                    f"(timeout: {timeout}s)"
                )
                raise SeleniumLockTimeoutError(session_id, timeout)
        else:
            # Sin timeout - espera indefinida (legacy behavior)
            await asyncio.to_thread(lock.acquire)
        
        try:
            yield
        finally:
            lock.release()
    
    @classmethod
    def remove_lock(cls, session_id: str) -> bool:
        """
        Elimina el lock de una sesion (llamar al cerrar la sesion).
        
        Solo elimina el lock si no esta adquirido actualmente.
        
        Args:
            session_id: ID de la sesion cuyo lock se quiere eliminar
            
        Returns:
            True si se elimino el lock, False si no existia o esta en uso
        """
        with cls._meta_lock:
            lock = cls._locks.get(session_id)
            if lock is None:
                return False
            
            # Intentar adquirir sin bloquear para verificar si esta libre
            if lock.acquire(blocking=False):
                # Esta libre, podemos eliminarlo
                lock.release()
                del cls._locks[session_id]
                logger.debug(f"Lock eliminado para sesion: {session_id}")
                return True
            else:
                # Esta en uso, no eliminamos
                logger.warning(
                    f"No se puede eliminar lock para sesion {session_id}: en uso"
                )
                return False
    
    @classmethod
    def get_active_locks_count(cls) -> int:
        """Retorna el numero de locks activos (para monitoreo)."""
        with cls._meta_lock:
            return len(cls._locks)


