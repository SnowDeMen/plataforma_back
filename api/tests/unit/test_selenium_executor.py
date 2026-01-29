"""
Tests unitarios para selenium_executor.py.

Verifica la funcionalidad del ThreadPoolExecutor dedicado y el semaforo global
para operaciones de Selenium.
"""
from __future__ import annotations

import asyncio
import time
from typing import List

import pytest

from app.infrastructure.driver.selenium_executor import (
    run_selenium,
    run_selenium_with_timeout,
    get_executor_stats,
    SELENIUM_MAX_WORKERS,
    SELENIUM_MAX_CONCURRENT_OPS,
)


class TestRunSelenium:
    """Tests para la funcion run_selenium()."""

    @pytest.mark.asyncio
    async def test_run_selenium_executes_function(self) -> None:
        """Verifica que ejecuta la funcion y retorna el resultado."""
        def simple_function() -> str:
            return "resultado"
        
        result = await run_selenium(simple_function)
        
        assert result == "resultado"

    @pytest.mark.asyncio
    async def test_run_selenium_with_args(self) -> None:
        """Verifica que pasa argumentos posicionales correctamente."""
        def function_with_args(a: int, b: int) -> int:
            return a + b
        
        result = await run_selenium(function_with_args, 5, 3)
        
        assert result == 8

    @pytest.mark.asyncio
    async def test_run_selenium_with_kwargs(self) -> None:
        """Verifica que pasa kwargs correctamente via partial."""
        def function_with_kwargs(name: str, prefix: str = "") -> str:
            return f"{prefix}{name}"
        
        result = await run_selenium(function_with_kwargs, "test", prefix="hello_")
        
        assert result == "hello_test"

    @pytest.mark.asyncio
    async def test_run_selenium_propagates_exception(self) -> None:
        """Verifica que propaga excepciones de la funcion ejecutada."""
        def function_that_raises() -> None:
            raise ValueError("Error de prueba")
        
        with pytest.raises(ValueError, match="Error de prueba"):
            await run_selenium(function_that_raises)

    @pytest.mark.asyncio
    async def test_run_selenium_executes_in_thread(self) -> None:
        """Verifica que la funcion se ejecuta en un thread separado."""
        import threading
        main_thread_id = threading.current_thread().ident
        execution_thread_id: List[int] = []
        
        def capture_thread_id() -> None:
            execution_thread_id.append(threading.current_thread().ident)
        
        await run_selenium(capture_thread_id)
        
        assert len(execution_thread_id) == 1
        assert execution_thread_id[0] != main_thread_id

    @pytest.mark.asyncio
    async def test_run_selenium_concurrent_execution(self) -> None:
        """Verifica que multiples operaciones pueden ejecutarse concurrentemente."""
        results: List[int] = []
        
        def slow_function(id: int) -> int:
            time.sleep(0.05)
            results.append(id)
            return id
        
        # Ejecutar 3 operaciones concurrentes
        tasks = [run_selenium(slow_function, i) for i in range(3)]
        returned = await asyncio.gather(*tasks)
        
        # Todas deben completar
        assert sorted(returned) == [0, 1, 2]
        assert sorted(results) == [0, 1, 2]


class TestRunSeleniumWithTimeout:
    """Tests para la funcion run_selenium_with_timeout()."""

    @pytest.mark.asyncio
    async def test_run_selenium_with_timeout_success(self) -> None:
        """Verifica que operacion rapida completa exitosamente."""
        def quick_function() -> str:
            return "rapido"
        
        result = await run_selenium_with_timeout(quick_function, timeout_seconds=5.0)
        
        assert result == "rapido"

    @pytest.mark.asyncio
    async def test_run_selenium_with_timeout_with_args(self) -> None:
        """Verifica que pasa argumentos correctamente."""
        def add(a: int, b: int) -> int:
            return a + b
        
        result = await run_selenium_with_timeout(add, 10, 20, timeout_seconds=5.0)
        
        assert result == 30

    @pytest.mark.asyncio
    async def test_run_selenium_with_timeout_raises_on_timeout(self) -> None:
        """Verifica que lanza TimeoutError si la operacion excede el timeout."""
        def slow_function() -> str:
            time.sleep(2.0)  # Mas largo que el timeout
            return "lento"
        
        with pytest.raises(asyncio.TimeoutError):
            await run_selenium_with_timeout(slow_function, timeout_seconds=0.1)

    @pytest.mark.asyncio
    async def test_run_selenium_with_timeout_propagates_exception(self) -> None:
        """Verifica que propaga excepciones de la funcion."""
        def function_that_raises() -> None:
            raise RuntimeError("Error en funcion")
        
        with pytest.raises(RuntimeError, match="Error en funcion"):
            await run_selenium_with_timeout(function_that_raises, timeout_seconds=5.0)


class TestGetExecutorStats:
    """Tests para la funcion get_executor_stats()."""

    def test_get_executor_stats_returns_correct_structure(self) -> None:
        """Verifica que retorna un dict con la estructura correcta."""
        stats = get_executor_stats()
        
        assert isinstance(stats, dict)
        assert "thread_pool" in stats
        assert "semaphore" in stats

    def test_get_executor_stats_thread_pool_info(self) -> None:
        """Verifica informacion del thread pool."""
        stats = get_executor_stats()
        
        thread_pool = stats["thread_pool"]
        assert thread_pool["max_workers"] == SELENIUM_MAX_WORKERS
        assert thread_pool["thread_name_prefix"] == "selenium-"

    def test_get_executor_stats_semaphore_info(self) -> None:
        """Verifica informacion del semaforo."""
        stats = get_executor_stats()
        
        semaphore = stats["semaphore"]
        assert semaphore["max_concurrent_ops"] == SELENIUM_MAX_CONCURRENT_OPS

    @pytest.mark.asyncio
    async def test_get_executor_stats_semaphore_available_slots(self) -> None:
        """Verifica que available_slots se actualiza correctamente."""
        # Forzar creacion del semaforo ejecutando una operacion
        await run_selenium(lambda: None)
        
        stats = get_executor_stats()
        
        # Cuando no hay operaciones en curso, todos los slots deben estar disponibles
        assert stats["semaphore"]["available_slots"] == SELENIUM_MAX_CONCURRENT_OPS


class TestConstants:
    """Tests para verificar constantes de configuracion."""

    def test_max_workers_is_positive(self) -> None:
        """Verifica que max_workers es un numero positivo."""
        assert SELENIUM_MAX_WORKERS > 0

    def test_max_concurrent_ops_is_positive(self) -> None:
        """Verifica que max_concurrent_ops es un numero positivo."""
        assert SELENIUM_MAX_CONCURRENT_OPS > 0

    def test_default_values(self) -> None:
        """Verifica valores por defecto esperados."""
        assert SELENIUM_MAX_WORKERS == 8
        assert SELENIUM_MAX_CONCURRENT_OPS == 8
