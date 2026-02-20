"""
Test manual para verificar el flujo de sincronizacion TP.

Este test verifica que:
1. Se puede crear driver navegando a #home
2. Login con cookies funciona
3. Navegacion a #home funciona
4. Busqueda de atleta por username funciona
5. Todas las operaciones usan run_selenium() correctamente

Ejecutar con:
    cd plataforma_back/api
    SELENIUM_HEADLESS=false python -m tests.manual.test_tp_sync_flow

Nota: Requiere cookies de TrainingPeaks validas y un username de atleta valido.
"""
import asyncio
import sys
from pathlib import Path

# Agregar path para imports
api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))

from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.selenium_executor import run_selenium, get_executor_stats
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService


async def test_tp_sync_flow(username: str):
    """
    Prueba el flujo de sincronizacion TP usando run_selenium().
    
    Args:
        username: Username de TrainingPeaks del atleta a buscar
    """
    print(f"\n{'='*70}")
    print(f"TEST: Flujo de sincronizacion TP")
    print(f"Username a buscar: {username}")
    print(f"{'='*70}\n")
    
    driver = None
    wait = None
    
    try:
        # Mostrar estadisticas iniciales
        stats = get_executor_stats()
        print(f"[INFO] ThreadPool: max_workers={stats['thread_pool']['max_workers']}, "
              f"semaphore_slots={stats['semaphore']['available_slots']}")
        print()
        
        # 1. Crear driver navegando a #home
        print("[1/5] Creando driver y navegando a #home...")
        driver, wait = await run_selenium(DriverManager._create_driver_for_home)
        print(f"      Driver creado exitosamente")
        print(f"      URL: {driver.current_url}")
        print()
        
        # 2. Inicializar servicios
        print("[2/5] Inicializando servicios...")
        auth_service = AuthService(driver, wait)
        athlete_service = AthleteService(driver, wait)
        print("      Servicios inicializados")
        print()
        
        # 3. Login con cookies
        print("[3/5] Haciendo login con cookies...")
        await run_selenium(auth_service.login_with_cookie)
        print("      Login exitoso")
        print(f"      URL despues de login: {driver.current_url}")
        print()
        
        # 4. Navegar a #home
        print("[4/5] Navegando a #home...")
        await run_selenium(athlete_service.navigate_to_home)
        print("      Navegacion exitosa")
        print(f"      URL: {driver.current_url}")
        print()
        
        # 5. Buscar atleta por username
        print(f"[5/5] Buscando atleta con username '{username}'...")
        search_result = await run_selenium(
            athlete_service.find_athlete_by_username,
            username
        )
        
        print(f"\n{'='*70}")
        print("RESULTADO DE BUSQUEDA:")
        
        if search_result.get("found"):
            print(f"  - Encontrado: SI")
            print(f"  - Nombre completo: {search_result.get('full_name', 'N/A')}")
            print(f"  - Grupo: {search_result.get('group', 'N/A')}")
            print(f"\n  Estado: EXITO")
            return True
        else:
            print(f"  - Encontrado: NO")
            print(f"  - Mensaje: {search_result.get('message', 'Sin mensaje')}")
            print(f"\n  Estado: FALLO (atleta no encontrado)")
            return False
            
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
                await run_selenium(driver.quit)
                print("Driver cerrado")
            except Exception as e:
                print(f"Error cerrando driver: {e}")


async def list_available_athletes():
    """
    Lista los atletas disponibles en TrainingPeaks para ayudar a elegir username.
    """
    print(f"\n{'='*70}")
    print("LISTANDO ATLETAS DISPONIBLES")
    print(f"{'='*70}\n")
    
    driver = None
    
    try:
        # Crear driver
        print("[1/3] Creando driver...")
        driver, wait = await run_selenium(DriverManager._create_driver_for_home)
        
        # Login
        print("[2/3] Haciendo login...")
        auth_service = AuthService(driver, wait)
        await run_selenium(auth_service.login_with_cookie)
        
        # Navegar a home
        print("[3/3] Navegando a #home...")
        athlete_service = AthleteService(driver, wait)
        await run_selenium(athlete_service.navigate_to_home)
        
        print("\nNavegador abierto en #home. Puedes ver los atletas disponibles.")
        print("Busca el username en la lista de atletas.")
        
        input("\nPresiona ENTER cuando hayas terminado...")
        
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        if driver:
            await run_selenium(driver.quit)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        username = sys.argv[1]
    else:
        print("Uso: python -m tests.manual.test_tp_sync_flow <username>")
        print("\nOpciones:")
        print("  1. Ingresar username manualmente")
        print("  2. Listar atletas disponibles primero")
        
        choice = input("\nElige (1/2): ").strip()
        
        if choice == "2":
            asyncio.run(list_available_athletes())
            username = input("\nIngresa el username del atleta: ").strip()
        else:
            username = input("Ingresa el username del atleta: ").strip()
    
    if not username:
        print("Error: Se requiere un username")
        sys.exit(1)
    
    result = asyncio.run(test_tp_sync_flow(username))
    
    print(f"\n{'='*70}")
    print(f"TEST {'PASSED' if result else 'FAILED'}")
    print(f"{'='*70}")
    
    sys.exit(0 if result else 1)
