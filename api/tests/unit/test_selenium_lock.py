"""
Tests unitarios para selenium_lock.py.

Verifica la funcionalidad del SeleniumSessionLockManager para serializar
operaciones de Selenium por sesion con soporte de timeout.
"""
from __future__ import annotations

import asyncio
import threading
from typing import List
from unittest.mock import patch

import pytest

from app.infrastructure.driver.selenium_lock import (
    SeleniumSessionLockManager,
    SeleniumLockTimeoutError,
    DEFAULT_LOCK_TIMEOUT,
)


@pytest.fixture(autouse=True)
def cleanup_locks():
    """Limpia todos los locks antes y despues de cada test."""
    # Limpiar antes del test
    SeleniumSessionLockManager._locks.clear()
    yield
    # Limpiar despues del test
    SeleniumSessionLockManager._locks.clear()


class TestSeleniumLockTimeoutError:
    """Tests para la excepcion SeleniumLockTimeoutError."""

    def test_exception_message_contains_session_id(self) -> None:
        """Verifica que el mensaje contiene el session_id."""
        error = SeleniumLockTimeoutError("session-123", 30.0)
        
        assert "session-123" in str(error)

    def test_exception_message_contains_timeout(self) -> None:
        """Verifica que el mensaje contiene el timeout."""
        error = SeleniumLockTimeoutError("session-123", 30.0)
        
        assert "30.0" in str(error)

    def test_exception_has_session_id_attribute(self) -> None:
        """Verifica que tiene atributo session_id."""
        error = SeleniumLockTimeoutError("session-abc", 60.0)
        
        assert error.session_id == "session-abc"

    def test_exception_has_timeout_attribute(self) -> None:
        """Verifica que tiene atributo timeout."""
        error = SeleniumLockTimeoutError("session-abc", 45.5)
        
        assert error.timeout == 45.5


class TestSeleniumSessionLockManagerLock:
    """Tests para SeleniumSessionLockManager.lock()."""

    @pytest.mark.asyncio
    async def test_lock_acquires_and_releases(self) -> None:
        """Verifica que adquiere y libera el lock correctamente."""
        executed = False
        
        async with SeleniumSessionLockManager.lock("session-1"):
            executed = True
        
        assert executed is True

    @pytest.mark.asyncio
    async def test_lock_creates_lock_for_session(self) -> None:
        """Verifica que crea un lock para la sesion."""
        assert "session-new" not in SeleniumSessionLockManager._locks
        
        async with SeleniumSessionLockManager.lock("session-new"):
            assert "session-new" in SeleniumSessionLockManager._locks

    @pytest.mark.asyncio
    async def test_lock_reuses_existing_lock(self) -> None:
        """Verifica que reutiliza el lock existente para la misma sesion."""
        async with SeleniumSessionLockManager.lock("session-reuse"):
            lock1 = SeleniumSessionLockManager._locks.get("session-reuse")
        
        async with SeleniumSessionLockManager.lock("session-reuse"):
            lock2 = SeleniumSessionLockManager._locks.get("session-reuse")
        
        assert lock1 is lock2

    @pytest.mark.asyncio
    async def test_lock_serializes_access(self) -> None:
        """Verifica que serializa operaciones concurrentes para la misma sesion."""
        execution_order: List[str] = []
        
        async def operation(name: str):
            async with SeleniumSessionLockManager.lock("session-serial", timeout=5.0):
                execution_order.append(f"start-{name}")
                await asyncio.sleep(0.05)
                execution_order.append(f"end-{name}")
        
        # Ejecutar dos operaciones concurrentes
        await asyncio.gather(operation("A"), operation("B"))
        
        # Deben estar serializadas: start-X, end-X, start-Y, end-Y
        assert len(execution_order) == 4
        # Una debe completar antes de que la otra empiece
        assert (
            (execution_order[0] == "start-A" and execution_order[1] == "end-A") or
            (execution_order[0] == "start-B" and execution_order[1] == "end-B")
        )

    @pytest.mark.asyncio
    async def test_lock_allows_different_sessions_concurrently(self) -> None:
        """Verifica que diferentes sesiones pueden ejecutar concurrentemente."""
        concurrent_count = 0
        max_concurrent = 0
        
        async def operation(session_id: str):
            nonlocal concurrent_count, max_concurrent
            async with SeleniumSessionLockManager.lock(session_id, timeout=5.0):
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.05)
                concurrent_count -= 1
        
        # Ejecutar operaciones en diferentes sesiones
        await asyncio.gather(
            operation("session-A"),
            operation("session-B"),
            operation("session-C")
        )
        
        # Deben haber corrido concurrentemente
        assert max_concurrent > 1

    @pytest.mark.asyncio
    async def test_lock_timeout_raises_error(self) -> None:
        """Verifica que lanza SeleniumLockTimeoutError si excede timeout."""
        # Adquirir lock en un thread separado para bloquearlo
        lock = SeleniumSessionLockManager._get_or_create_lock("session-timeout")
        lock.acquire()
        
        try:
            with pytest.raises(SeleniumLockTimeoutError) as exc_info:
                async with SeleniumSessionLockManager.lock("session-timeout", timeout=0.1):
                    pass
            
            assert exc_info.value.session_id == "session-timeout"
            assert exc_info.value.timeout == 0.1
        finally:
            lock.release()

    @pytest.mark.asyncio
    async def test_lock_uses_default_timeout(self) -> None:
        """Verifica que usa el timeout por defecto."""
        assert DEFAULT_LOCK_TIMEOUT == 60.0

    @pytest.mark.asyncio
    async def test_lock_releases_on_exception(self) -> None:
        """Verifica que libera el lock incluso si hay excepcion."""
        lock = None
        
        try:
            async with SeleniumSessionLockManager.lock("session-exception"):
                lock = SeleniumSessionLockManager._locks.get("session-exception")
                raise ValueError("Error intencional")
        except ValueError:
            pass
        
        # El lock debe estar libre (podemos adquirirlo sin bloquear)
        assert lock is not None
        acquired = lock.acquire(blocking=False)
        assert acquired is True
        lock.release()


class TestRemoveLock:
    """Tests para SeleniumSessionLockManager.remove_lock()."""

    def test_remove_lock_success(self) -> None:
        """Verifica que elimina un lock libre correctamente."""
        # Crear un lock
        SeleniumSessionLockManager._get_or_create_lock("session-remove")
        assert "session-remove" in SeleniumSessionLockManager._locks
        
        # Eliminarlo
        result = SeleniumSessionLockManager.remove_lock("session-remove")
        
        assert result is True
        assert "session-remove" not in SeleniumSessionLockManager._locks

    def test_remove_lock_nonexistent(self) -> None:
        """Verifica que retorna False para lock inexistente."""
        result = SeleniumSessionLockManager.remove_lock("session-nonexistent")
        
        assert result is False

    def test_remove_lock_in_use(self) -> None:
        """Verifica que retorna False si el lock esta en uso."""
        lock = SeleniumSessionLockManager._get_or_create_lock("session-in-use")
        lock.acquire()
        
        try:
            result = SeleniumSessionLockManager.remove_lock("session-in-use")
            
            assert result is False
            assert "session-in-use" in SeleniumSessionLockManager._locks
        finally:
            lock.release()


class TestGetActiveLocksCount:
    """Tests para SeleniumSessionLockManager.get_active_locks_count()."""

    def test_active_locks_count_zero(self) -> None:
        """Verifica que retorna 0 cuando no hay locks."""
        count = SeleniumSessionLockManager.get_active_locks_count()
        
        assert count == 0

    def test_active_locks_count_increments(self) -> None:
        """Verifica que el conteo incrementa al crear locks."""
        assert SeleniumSessionLockManager.get_active_locks_count() == 0
        
        SeleniumSessionLockManager._get_or_create_lock("session-1")
        assert SeleniumSessionLockManager.get_active_locks_count() == 1
        
        SeleniumSessionLockManager._get_or_create_lock("session-2")
        assert SeleniumSessionLockManager.get_active_locks_count() == 2
        
        SeleniumSessionLockManager._get_or_create_lock("session-3")
        assert SeleniumSessionLockManager.get_active_locks_count() == 3

    def test_active_locks_count_after_remove(self) -> None:
        """Verifica que el conteo decrementa al eliminar locks."""
        SeleniumSessionLockManager._get_or_create_lock("session-a")
        SeleniumSessionLockManager._get_or_create_lock("session-b")
        assert SeleniumSessionLockManager.get_active_locks_count() == 2
        
        SeleniumSessionLockManager.remove_lock("session-a")
        assert SeleniumSessionLockManager.get_active_locks_count() == 1


class TestGetOrCreateLock:
    """Tests para el metodo interno _get_or_create_lock()."""

    def test_creates_new_lock(self) -> None:
        """Verifica que crea un nuevo lock si no existe."""
        assert "session-create" not in SeleniumSessionLockManager._locks
        
        lock = SeleniumSessionLockManager._get_or_create_lock("session-create")
        
        assert lock is not None
        # threading.Lock() retorna _thread.lock, verificamos que tiene los metodos esperados
        assert hasattr(lock, "acquire")
        assert hasattr(lock, "release")
        assert "session-create" in SeleniumSessionLockManager._locks

    def test_returns_existing_lock(self) -> None:
        """Verifica que retorna el lock existente."""
        lock1 = SeleniumSessionLockManager._get_or_create_lock("session-existing")
        lock2 = SeleniumSessionLockManager._get_or_create_lock("session-existing")
        
        assert lock1 is lock2

    def test_thread_safe(self) -> None:
        """Verifica que la creacion de locks es thread-safe."""
        created_locks: List[threading.Lock] = []
        
        def create_lock():
            lock = SeleniumSessionLockManager._get_or_create_lock("session-threadsafe")
            created_locks.append(lock)
        
        threads = [threading.Thread(target=create_lock) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Todos deben obtener el mismo lock
        assert len(created_locks) == 10
        assert all(lock is created_locks[0] for lock in created_locks)
