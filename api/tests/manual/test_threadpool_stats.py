"""
Test manual para verificar estadisticas del ThreadPool y semaforo de Selenium.

Este test verifica que:
1. get_executor_stats() retorna informacion correcta
2. El semaforo limita la concurrencia correctamente
3. Las operaciones se ejecutan en threads separados
4. El ThreadPool no se bloquea con multiples operaciones

Ejecutar con:
    cd plataforma_back/api
    python -m tests.manual.test_threadpool_stats

Nota: Este test NO requiere TrainingPeaks real, usa funciones mock.
"""
import asyncio
import sys
import time
import threading
from pathlib import Path
from typing import List

# Agregar path para imports
api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))

from app.infrastructure.driver.selenium_executor import (
    run_selenium,
    run_selenium_with_timeout,
    get_executor_stats,
    SELENIUM_MAX_WORKERS,
    SELENIUM_MAX_CONCURRENT_OPS,
)


async def test_executor_stats():
    """Prueba que get_executor_stats() retorna informacion correcta."""
    print(f"\n{'='*70}")
    print("TEST 1: Verificar get_executor_stats()")
    print(f"{'='*70}\n")
    
    # Forzar creacion del semaforo ejecutando una operacion simple
    await run_selenium(lambda: None)
    
    stats = get_executor_stats()
    
    print("Estadisticas del executor:")
    print(f"  thread_pool.max_workers: {stats['thread_pool']['max_workers']}")
    print(f"  thread_pool.thread_name_prefix: {stats['thread_pool']['thread_name_prefix']}")
    print(f"  semaphore.max_concurrent_ops: {stats['semaphore']['max_concurrent_ops']}")
    print(f"  semaphore.available_slots: {stats['semaphore']['available_slots']}")
    
    # Verificaciones
    checks = []
    
    # Check max_workers
    if stats['thread_pool']['max_workers'] == SELENIUM_MAX_WORKERS:
        print(f"\n  [OK] max_workers es {SELENIUM_MAX_WORKERS}")
        checks.append(True)
    else:
        print(f"\n  [FAIL] max_workers esperado {SELENIUM_MAX_WORKERS}, obtenido {stats['thread_pool']['max_workers']}")
        checks.append(False)
    
    # Check prefix
    if stats['thread_pool']['thread_name_prefix'] == "selenium-":
        print(f"  [OK] thread_name_prefix es 'selenium-'")
        checks.append(True)
    else:
        print(f"  [FAIL] thread_name_prefix incorrecto")
        checks.append(False)
    
    # Check semaphore
    if stats['semaphore']['max_concurrent_ops'] == SELENIUM_MAX_CONCURRENT_OPS:
        print(f"  [OK] max_concurrent_ops es {SELENIUM_MAX_CONCURRENT_OPS}")
        checks.append(True)
    else:
        print(f"  [FAIL] max_concurrent_ops incorrecto")
        checks.append(False)
    
    return all(checks)


async def test_thread_execution():
    """Prueba que las operaciones se ejecutan en threads separados."""
    print(f"\n{'='*70}")
    print("TEST 2: Verificar ejecucion en threads separados")
    print(f"{'='*70}\n")
    
    main_thread_id = threading.current_thread().ident
    execution_thread_ids: List[int] = []
    
    def capture_thread():
        tid = threading.current_thread().ident
        tname = threading.current_thread().name
        execution_thread_ids.append(tid)
        return (tid, tname)
    
    print(f"Thread principal: {main_thread_id} ({threading.current_thread().name})")
    
    # Ejecutar varias operaciones
    results = []
    for i in range(3):
        tid, tname = await run_selenium(capture_thread)
        results.append((tid, tname))
        print(f"  Operacion {i+1}: thread={tid} ({tname})")
    
    # Verificar que son threads diferentes al principal
    all_different = all(tid != main_thread_id for tid in execution_thread_ids)
    
    if all_different:
        print(f"\n  [OK] Todas las operaciones se ejecutaron en threads separados")
        
        # Verificar que los threads tienen el prefijo correcto
        all_selenium_prefix = all("selenium-" in name for _, name in results)
        if all_selenium_prefix:
            print(f"  [OK] Todos los threads tienen prefijo 'selenium-'")
            return True
        else:
            print(f"  [FAIL] Algunos threads no tienen prefijo 'selenium-'")
            return False
    else:
        print(f"\n  [FAIL] Algunas operaciones se ejecutaron en el thread principal")
        return False


async def test_semaphore_limiting():
    """Prueba que el semaforo limita la concurrencia."""
    print(f"\n{'='*70}")
    print("TEST 3: Verificar limitacion del semaforo")
    print(f"{'='*70}\n")
    
    concurrent_count = 0
    max_concurrent_observed = 0
    execution_log: List[str] = []
    lock = threading.Lock()
    
    def slow_operation(op_id: int):
        nonlocal concurrent_count, max_concurrent_observed
        
        with lock:
            concurrent_count += 1
            max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
            execution_log.append(f"start-{op_id} (concurrent={concurrent_count})")
        
        time.sleep(0.3)  # Simular operacion lenta
        
        with lock:
            concurrent_count -= 1
            execution_log.append(f"end-{op_id} (concurrent={concurrent_count})")
        
        return op_id
    
    # Ejecutar mas operaciones que el limite del semaforo
    num_operations = SELENIUM_MAX_CONCURRENT_OPS + 4
    print(f"Ejecutando {num_operations} operaciones concurrentes...")
    print(f"Limite del semaforo: {SELENIUM_MAX_CONCURRENT_OPS}")
    
    start_time = time.time()
    tasks = [run_selenium(slow_operation, i) for i in range(num_operations)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    print(f"\nTiempo total: {elapsed:.2f}s")
    print(f"Maxima concurrencia observada: {max_concurrent_observed}")
    print(f"Limite esperado: {SELENIUM_MAX_CONCURRENT_OPS}")
    
    # Mostrar log de ejecucion
    print(f"\nLog de ejecucion (primeros 10 eventos):")
    for event in execution_log[:10]:
        print(f"  {event}")
    if len(execution_log) > 10:
        print(f"  ... ({len(execution_log) - 10} eventos mas)")
    
    # Verificar que el semaforo limito la concurrencia
    if max_concurrent_observed <= SELENIUM_MAX_CONCURRENT_OPS:
        print(f"\n  [OK] El semaforo limito la concurrencia a {max_concurrent_observed}")
        return True
    else:
        print(f"\n  [FAIL] Se excedio el limite del semaforo")
        return False


async def test_timeout_functionality():
    """Prueba que run_selenium_with_timeout funciona correctamente."""
    print(f"\n{'='*70}")
    print("TEST 4: Verificar timeout en run_selenium_with_timeout")
    print(f"{'='*70}\n")
    
    # Test 1: Operacion rapida (deberia completar)
    print("Test 4a: Operacion rapida (timeout=5s)...")
    
    def quick_op():
        time.sleep(0.1)
        return "rapido"
    
    try:
        result = await run_selenium_with_timeout(quick_op, timeout_seconds=5.0)
        if result == "rapido":
            print("  [OK] Operacion rapida completo exitosamente")
            test_4a = True
        else:
            print(f"  [FAIL] Resultado inesperado: {result}")
            test_4a = False
    except Exception as e:
        print(f"  [FAIL] Error inesperado: {e}")
        test_4a = False
    
    # Test 2: Operacion lenta (deberia hacer timeout)
    print("\nTest 4b: Operacion lenta (timeout=0.1s)...")
    
    def slow_op():
        time.sleep(2.0)
        return "lento"
    
    try:
        result = await run_selenium_with_timeout(slow_op, timeout_seconds=0.1)
        print(f"  [FAIL] No hizo timeout, resultado: {result}")
        test_4b = False
    except asyncio.TimeoutError:
        print("  [OK] Timeout lanzado correctamente")
        test_4b = True
    except Exception as e:
        print(f"  [FAIL] Error inesperado: {type(e).__name__}: {e}")
        test_4b = False
    
    return test_4a and test_4b


async def run_all_tests():
    """Ejecuta todos los tests."""
    print(f"\n{'='*70}")
    print("TESTS DE THREADPOOL Y SEMAFORO DE SELENIUM")
    print(f"{'='*70}")
    print(f"\nConfiguracion:")
    print(f"  SELENIUM_MAX_WORKERS: {SELENIUM_MAX_WORKERS}")
    print(f"  SELENIUM_MAX_CONCURRENT_OPS: {SELENIUM_MAX_CONCURRENT_OPS}")
    
    results = {}
    
    # Test 1
    results['executor_stats'] = await test_executor_stats()
    
    # Test 2
    results['thread_execution'] = await test_thread_execution()
    
    # Test 3
    results['semaphore_limiting'] = await test_semaphore_limiting()
    
    # Test 4
    results['timeout'] = await test_timeout_functionality()
    
    # Resumen
    print(f"\n{'='*70}")
    print("RESUMEN DE TESTS")
    print(f"{'='*70}")
    
    for test_name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    
    print(f"\n{'='*70}")
    print(f"RESULTADO FINAL: {'TODOS LOS TESTS PASARON' if all_passed else 'ALGUNOS TESTS FALLARON'}")
    print(f"{'='*70}")
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(run_all_tests())
    sys.exit(0 if result else 1)
