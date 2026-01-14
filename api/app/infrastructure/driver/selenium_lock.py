"""
Lock de Selenium por sesión.

Motivación:
- El driver de Selenium NO es seguro para uso concurrente.
- En este proyecto, varias rutas (chat/MCP/historial) pueden intentar usar
  el mismo driver asociado a `session_id`.
- Necesitamos serializar el acceso sin introducir dependencias externas.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict


class SeleniumSessionLockManager:
    """
    Gestor de locks por `session_id`.

    Implementación:
    - Usa `threading.Lock` por compatibilidad con código síncrono.
    - La adquisición se ejecuta en un thread vía `asyncio.to_thread` para
      no bloquear el event loop.
    """

    _locks: Dict[str, threading.Lock] = {}
    _meta_lock = threading.Lock()

    @classmethod
    def _get_or_create_lock(cls, session_id: str) -> threading.Lock:
        with cls._meta_lock:
            lock = cls._locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                cls._locks[session_id] = lock
            return lock

    @classmethod
    @asynccontextmanager
    async def lock(cls, session_id: str) -> AsyncIterator[None]:
        lock = cls._get_or_create_lock(session_id)
        await asyncio.to_thread(lock.acquire)
        try:
            yield
        finally:
            lock.release()


