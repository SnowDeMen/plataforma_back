"""
Test manual para verificar la seleccion de atleta en TrainingPeaks.

Este script:
1. Abre Chrome y navega a TrainingPeaks
2. Hace login
3. Abre Athlete Library
4. Intenta seleccionar un atleta por nombre
5. Espera 5 segundos
6. Verifica si el atleta seleccionado es el correcto
7. Muestra el resultado

Ejecutar con:
    python -m tests.manual.test_athlete_selection
"""
import time
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Agregar el path para imports
sys.path.insert(0, "/Users/luisaragon/Documents/Neuronomy/Development/plataforma/plataforma_back/api")

from app.infrastructure.driver.driver_manager import DriverManager
from app.infrastructure.driver.services.athlete_service import AthleteService


def test_athlete_selection(athlete_name: str = "Luis Aragon"):
    """
    Prueba la seleccion de un atleta en TrainingPeaks.
    
    Args:
        athlete_name: Nombre del atleta a seleccionar
    """
    print(f"\n{'='*60}")
    print(f"TEST: Seleccion de atleta '{athlete_name}'")
    print(f"{'='*60}\n")
    
    driver = None
    session = None
    
    try:
        # 1. Crear sesion y hacer login
        print("[1/5] Creando sesion y haciendo login...")
        session = DriverManager.create_session(athlete_name)
        driver = session.driver
        
        # Login
        session.auth_service.login_with_cookie()
        print("      Login exitoso")
        
        # 2. Abrir Athlete Library
        print("[2/5] Abriendo Athlete Library...")
        session.athlete_service.click_athlete_library()
        session.athlete_service.expand_all_athlete_libraries()
        print("      Athlete Library abierta")
        
        # 3. Buscar el tile del atleta
        print(f"[3/5] Buscando tile de '{athlete_name}'...")
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data_cy='itemsContainer']")))
        
        # XPath actual
        xpath = (
            "//div[@data_cy='athleteTileName']"
            f"/span[normalize-space(text()) = '{athlete_name}']"
            "/ancestor::div[contains(@class,'athleteTile') and not(contains(@class,'Container'))]"
        )
        
        try:
            tile = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            print(f"      Tile encontrado: visible={tile.is_displayed()}, enabled={tile.is_enabled()}")
            
            # Mostrar info del tile
            tile_class = tile.get_attribute("class")
            print(f"      Clase del tile: '{tile_class}'")
            
        except Exception as e:
            print(f"      ERROR: No se encontro el tile con XPath")
            print(f"      XPath usado: {xpath}")
            
            # Intentar encontrar todos los tiles para debug
            print("\n      Buscando todos los tiles disponibles...")
            all_tiles = driver.find_elements(By.CSS_SELECTOR, "div.athleteTile")
            print(f"      Encontrados {len(all_tiles)} tiles con clase 'athleteTile'")
            
            for i, t in enumerate(all_tiles[:5]):  # Mostrar primeros 5
                try:
                    name_el = t.find_element(By.CSS_SELECTOR, "div.athleteTileName span")
                    print(f"        [{i}] '{name_el.text}' - class='{t.get_attribute('class')}'")
                except:
                    print(f"        [{i}] (no se pudo leer nombre)")
            
            return False
        
        # 4. Hacer click en el tile
        print("[4/5] Haciendo click en el tile...")
        
        # Scroll al elemento
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tile)
        time.sleep(0.3)
        
        # Click
        tile.click()
        print("      Click ejecutado")
        
        # 5. Esperar y verificar
        print("[5/5] Esperando 5 segundos y verificando...")
        time.sleep(5)
        
        # Verificar el atleta seleccionado
        try:
            selected_element = driver.find_element(By.CSS_SELECTOR, "div.selectedAthleteName span")
            selected_name = selected_element.text.strip()
            
            print(f"\n{'='*60}")
            print(f"RESULTADO:")
            print(f"  Atleta esperado:     '{athlete_name}'")
            print(f"  Atleta seleccionado: '{selected_name}'")
            
            if athlete_name.lower() in selected_name.lower() or selected_name.lower() in athlete_name.lower():
                print(f"  Estado: EXITO - El atleta fue seleccionado correctamente")
                return True
            else:
                print(f"  Estado: FALLO - El atleta seleccionado no coincide")
                return False
                
        except Exception as e:
            print(f"\n  ERROR al verificar: {e}")
            return False
        
    except Exception as e:
        print(f"\nERROR durante el test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print(f"\n{'='*60}")
        input("Presiona ENTER para cerrar el navegador...")
        
        if session:
            DriverManager.close_session(session.session_id)
            print("Sesion cerrada")


if __name__ == "__main__":
    # Nombre del atleta a probar (puede pasarse como argumento)
    athlete = sys.argv[1] if len(sys.argv) > 1 else "Luis Aragon"
    
    result = test_athlete_selection(athlete)
    
    print(f"\n{'='*60}")
    print(f"TEST {'PASSED' if result else 'FAILED'}")
    print(f"{'='*60}")
    
    sys.exit(0 if result else 1)
