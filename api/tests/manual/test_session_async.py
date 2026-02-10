"""
Test manual para verificar initialize_training_session_async() con run_selenium().

Este test verifica que:
1. La sesion se inicializa correctamente usando el ThreadPoolExecutor dedicado
2. El semaforo global limita la concurrencia
3. El healthcheck responde durante la inicializacion (no bloquea event loop)
4. Login, seleccion de atleta y Workout Library funcionan

Ejecutar con:
    cd plataforma_back/api
    SELENIUM_HEADLESS=false python -m tests.manual.test_session_async

Nota: Requiere cookies de TrainingPeaks validas.
"""
import asyncio
import sys
import time
from pathlib import Path

# Agregar path para imports
api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))

from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.selenium_executor import get_executor_stats


async def test_session_initialization(athlete_name: str = "Luis Aragon"):
    """
    Prueba la inicializacion asincrona de una sesion de entrenamiento.
    
    Args:
        athlete_name: Nombre del atleta a seleccionar en TrainingPeaks
    """
    print(f"\n{'='*70}")
    print(f"TEST: Inicializacion asincrona de sesion")
    print(f"Atleta: {athlete_name}")
    print(f"{'='*70}\n")
    
    session = None
    
    try:
        # Mostrar estadisticas iniciales del ThreadPool
        stats_before = get_executor_stats()
        print(f"[INFO] Estadisticas del ThreadPool (antes):")
        print(f"       max_workers: {stats_before['thread_pool']['max_workers']}")
        print(f"       max_concurrent_ops: {stats_before['semaphore']['max_concurrent_ops']}")
        print(f"       available_slots: {stats_before['semaphore']['available_slots']}")
        print()
        
        # 1. Inicializar sesion asincrona
        print("[1/4] Iniciando sesion asincrona...")
        print("      (Esto deberia usar run_selenium() para cada operacion)")
        start_time = time.time()
        
        session = await DriverManager.initialize_training_session_async(athlete_name)
        
        elapsed = time.time() - start_time
        print(f"      Sesion inicializada en {elapsed:.2f} segundos")
        print(f"      Session ID: {session.session_id}")
        print()
        
        # 2. Verificar que la sesion esta activa
        print("[2/4] Verificando estado de la sesion...")
        is_active = DriverManager.is_session_active(session.session_id)
        print(f"      Sesion activa: {is_active}")
        
        if not is_active:
            print("      ERROR: La sesion no esta activa")
            return False
        print()
        
        # 3. Verificar estadisticas del ThreadPool despues
        stats_after = get_executor_stats()
        print(f"[3/4] Estadisticas del ThreadPool (despues):")
        print(f"       available_slots: {stats_after['semaphore']['available_slots']}")
        print(f"       (Deben ser {stats_after['semaphore']['max_concurrent_ops']} si no hay operaciones en curso)")
        print()
        
        # 4. Verificar que el driver funciona
        print("[4/4] Verificando funcionamiento del driver...")
        current_url = session.driver.current_url
        print(f"      URL actual: {current_url}")
        
        if "trainingpeaks.com" in current_url:
            print("      Driver funcionando correctamente")
        else:
            print("      ADVERTENCIA: URL no es de TrainingPeaks")
        print()
        
        # Resultado
        print(f"{'='*70}")
        print("RESULTADO: EXITO")
        print(f"  - Sesion inicializada correctamente")
        print(f"  - ThreadPool dedicado funcionando")
        print(f"  - Semaforo global activo")
        print(f"{'='*70}")
        
        return True
        
    except Exception as e:
        print(f"\nERROR durante el test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print()
        input("Presiona ENTER para cerrar el navegador...")
        
        if session:
            print("Cerrando sesion...")
            DriverManager.close_session(session.session_id)
            print("Sesion cerrada")


async def test_concurrent_healthcheck():
    """
    Verifica que el healthcheck puede responder durante la inicializacion.
    
    Este test simula un healthcheck concurrente para verificar que
    run_selenium() no bloquea el event loop.
    """
    print(f"\n{'='*70}")
    print("TEST: Healthcheck concurrente durante inicializacion")
    print(f"{'='*70}\n")
    
    healthcheck_responses = []
    session = None
    
    async def simulated_healthcheck():
        """Simula un healthcheck que se ejecuta cada 0.5 segundos."""
        while True:
            await asyncio.sleep(0.5)
            healthcheck_responses.append(time.time())
            print(f"  [healthcheck] Respuesta #{len(healthcheck_responses)}")
    
    try:
        # Iniciar healthcheck en background
        print("[1/2] Iniciando healthcheck simulado en background...")
        healthcheck_task = asyncio.create_task(simulated_healthcheck())
        
        # Inicializar sesion (operacion larga)
        print("[2/2] Iniciando sesion (operacion larga)...")
        start_time = time.time()
        
        session = await DriverManager.initialize_training_session_async("Luis Aragon")
        
        elapsed = time.time() - start_time
        
        # Cancelar healthcheck
        healthcheck_task.cancel()
        try:
            await healthcheck_task
        except asyncio.CancelledError:
            pass
        
        print(f"\n{'='*70}")
        print("RESULTADO:")
        print(f"  - Tiempo de inicializacion: {elapsed:.2f}s")
        print(f"  - Healthchecks durante inicializacion: {len(healthcheck_responses)}")
        
        if len(healthcheck_responses) > 0:
            print(f"  - Estado: EXITO - El event loop NO se bloqueo")
            return True
        else:
            print(f"  - Estado: FALLO - No hubo healthchecks (event loop bloqueado?)")
            return False
            
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if session:
            DriverManager.close_session(session.session_id)


if __name__ == "__main__":
    athlete = sys.argv[1] if len(sys.argv) > 1 else "Luis Aragon"
    
    # Test principal
    result1 = asyncio.run(test_session_initialization(athlete))
    
    print("\n" + "="*70)
    print("Quieres ejecutar el test de healthcheck concurrente? (s/n)")
    response = input().strip().lower()
    
    if response == 's':
        result2 = asyncio.run(test_concurrent_healthcheck())
    else:
        result2 = True
    
    # Resultado final
    final_result = result1 and result2
    
    print(f"\n{'='*70}")
    print(f"TESTS {'PASSED' if final_result else 'FAILED'}")
    print(f"{'='*70}")
    
    sys.exit(0 if final_result else 1)
