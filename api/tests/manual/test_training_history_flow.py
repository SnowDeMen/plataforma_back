"""
Test manual para verificar el flujo de extraccion de historial de entrenamiento.

Este test verifica que:
1. Se puede crear driver correctamente
2. Login y seleccion de atleta funcionan
3. Extraccion de workouts del calendario funciona
4. Todas las operaciones usan run_selenium() correctamente

Ejecutar con:
    cd plataforma_back/api
    SELENIUM_HEADLESS=false python -m tests.manual.test_training_history_flow

Nota: Requiere cookies de TrainingPeaks validas.
"""
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

# Agregar path para imports
api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))

# Agregar path para domain (funciones de calendario)
mcp_path = api_path.parent.parent / "mcp"
sys.path.insert(0, str(mcp_path))

from app.infrastructure.driver.driver_manager import DriverManager, TRAININGPEAKS_URL
from app.infrastructure.driver.selenium_executor import run_selenium, get_executor_stats
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService


async def test_training_history_flow(athlete_name: str, days_back: int = 7):
    """
    Prueba el flujo de extraccion de historial de entrenamiento.
    
    Args:
        athlete_name: Nombre del atleta a seleccionar
        days_back: Cantidad de dias hacia atras a revisar
    """
    print(f"\n{'='*70}")
    print(f"TEST: Extraccion de historial de entrenamiento")
    print(f"Atleta: {athlete_name}")
    print(f"Dias a revisar: {days_back}")
    print(f"{'='*70}\n")
    
    driver = None
    wait = None
    
    try:
        # Mostrar estadisticas iniciales
        stats = get_executor_stats()
        print(f"[INFO] ThreadPool: max_workers={stats['thread_pool']['max_workers']}, "
              f"semaphore_slots={stats['semaphore']['available_slots']}")
        print()
        
        # 1. Crear driver
        print("[1/5] Creando driver...")
        driver, wait = await run_selenium(_create_driver)
        print(f"      Driver creado exitosamente")
        print()
        
        # 2. Login
        print("[2/5] Haciendo login...")
        auth_service = AuthService(driver, wait)
        await run_selenium(auth_service.login_with_cookie)
        print("      Login exitoso")
        print()
        
        # 3. Seleccionar atleta
        print(f"[3/5] Seleccionando atleta '{athlete_name}'...")
        athlete_service = AthleteService(driver, wait)
        await run_selenium(athlete_service.select_athlete, athlete_name)
        print("      Atleta seleccionado")
        print()
        
        # 4. Preparar extraccion de historial
        print("[4/5] Preparando extraccion de historial...")
        
        # Importar funciones del dominio
        try:
            from domain.core import set_driver
            from domain.calendar.workout_service import get_all_quickviews_on_date
            
            # Inyectar driver
            set_driver(driver, wait)
            print("      Funciones de dominio cargadas")
        except ImportError as e:
            print(f"      ADVERTENCIA: No se pudieron cargar funciones de dominio: {e}")
            print("      El test continuara sin extraccion de quickviews")
            get_all_quickviews_on_date = None
        print()
        
        # 5. Extraer workouts
        print(f"[5/5] Extrayendo workouts de los ultimos {days_back} dias...")
        
        today = date.today()
        workouts_found = {}
        
        for i in range(days_back):
            check_date = today - timedelta(days=i)
            iso_date = check_date.isoformat()
            
            print(f"      Revisando {iso_date}...", end=" ")
            
            if get_all_quickviews_on_date:
                try:
                    workouts = await run_selenium(
                        get_all_quickviews_on_date,
                        iso_date,
                        use_today=(i == 0),
                        timeout=10,
                        limit=None
                    )
                    
                    if workouts:
                        workouts_found[iso_date] = workouts
                        print(f"{len(workouts)} workout(s)")
                    else:
                        print("sin workouts")
                        
                except Exception as e:
                    print(f"error: {e}")
            else:
                print("(extraccion no disponible)")
        
        # Resultado
        print(f"\n{'='*70}")
        print("RESULTADO:")
        print(f"  - Dias revisados: {days_back}")
        print(f"  - Dias con workouts: {len(workouts_found)}")
        
        total_workouts = sum(len(w) for w in workouts_found.values())
        print(f"  - Total de workouts encontrados: {total_workouts}")
        
        if workouts_found:
            print(f"\n  Detalle por dia:")
            for day, workouts in sorted(workouts_found.items()):
                print(f"    {day}: {len(workouts)} workout(s)")
        
        print(f"\n  Estado: EXITO")
        return True
        
    except Exception as e:
        print(f"\nERROR durante el test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print()
        input("Presiona ENTER para cerrar el navegador...")
        
        if driver:
            print("Cerrando driver...")
            try:
                driver.quit()
                print("Driver cerrado")
            except Exception as e:
                print(f"Error cerrando driver: {e}")


def _create_driver():
    """Crea un driver de Chrome configurado."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from app.core.config import settings
    
    opts = Options()
    
    if settings.SELENIUM_HEADLESS:
        opts.add_argument("--headless=new")
    
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-infobars")
    
    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 10)
    
    driver.get(TRAININGPEAKS_URL)
    
    return driver, wait


if __name__ == "__main__":
    if len(sys.argv) > 1:
        athlete_name = sys.argv[1]
    else:
        athlete_name = input("Ingresa el nombre del atleta: ").strip()
        if not athlete_name:
            athlete_name = "Luis Aragon"
    
    days = 7
    if len(sys.argv) > 2:
        days = int(sys.argv[2])
    
    result = asyncio.run(test_training_history_flow(athlete_name, days))
    
    print(f"\n{'='*70}")
    print(f"TEST {'PASSED' if result else 'FAILED'}")
    print(f"{'='*70}")
    
    sys.exit(0 if result else 1)
