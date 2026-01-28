"""
Script de testing para probar la navegacion a #home y click en settings.

Este script permite probar de forma aislada los nuevos metodos de AthleteService
para busqueda de atletas por username.

Ejecutar con:
    cd plataforma_back/api
    export SELENIUM_HEADLESS=false
    python -m scripts.test_athlete_settings

Requiere:
    - Variables de entorno TP_EMAIL y TP_PASSWORD configuradas
    - SELENIUM_HEADLESS=false para ver el navegador (recomendado para debugging)
"""
import os
import sys
import time

import dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from loguru import logger

# Cargar variables de entorno
dotenv.load_dotenv()

# Agregar el path de la app al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService
from app.infrastructure.driver.driver_manager import TRAININGPEAKS_HOME_URL


def create_visible_driver() -> tuple[webdriver.Chrome, WebDriverWait]:
    """
    Crea un driver de Chrome en modo visible para debugging.
    
    Returns:
        tuple: (WebDriver, WebDriverWait)
    """
    opts = Options()
    
    # Forzar modo visible para testing
    headless = os.getenv("SELENIUM_HEADLESS", "false").lower() == "true"
    if headless:
        opts.add_argument("--headless=new")
        logger.warning("Ejecutando en modo headless. Para debugging, usar SELENIUM_HEADLESS=false")
    else:
        logger.info("Chrome iniciando con GUI (modo visible)")
    
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-infobars")
    
    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 15)
    
    return driver, wait


def pause_for_inspection(message: str = "Presiona Enter para continuar...") -> None:
    """
    Pausa la ejecucion para permitir inspeccion visual del navegador.
    
    Args:
        message: Mensaje a mostrar al usuario
    """
    input(f"\n>>> {message}\n")


def run_test():
    """
    Ejecuta el test completo de navegacion a #home y click en settings.
    """
    driver = None
    
    try:
        # =====================================================================
        # PASO 1: Crear driver
        # =====================================================================
        logger.info("=" * 60)
        logger.info("PASO 1: Creando driver de Chrome")
        logger.info("=" * 60)
        
        driver, wait = create_visible_driver()
        logger.info("Driver creado exitosamente")
        
        # =====================================================================
        # PASO 2: Navegar a #home
        # =====================================================================
        logger.info("=" * 60)
        logger.info("PASO 2: Navegando a TrainingPeaks #home")
        logger.info("=" * 60)
        
        driver.get(TRAININGPEAKS_HOME_URL)
        logger.info(f"URL cargada: {TRAININGPEAKS_HOME_URL}")
        
        # Inicializar servicios
        auth_service = AuthService(driver, wait)
        athlete_service = AthleteService(driver, wait)
        
        # =====================================================================
        # PASO 3: Cerrar cookie banner y hacer login
        # =====================================================================
        logger.info("=" * 60)
        logger.info("PASO 3: Login en TrainingPeaks")
        logger.info("=" * 60)
        
        auth_service.login_with_cookie()
        logger.info("Login completado")
        
        # Esperar un momento para que cargue la pagina post-login
        time.sleep(3)
        
        # =====================================================================
        # PASO 4: Navegar a #home (puede redirigir a otra pagina despues del login)
        # =====================================================================
        logger.info("=" * 60)
        logger.info("PASO 4: Asegurar navegacion a #home")
        logger.info("=" * 60)
        
        athlete_service.navigate_to_home()
        logger.info("Pagina #home cargada")
        
        pause_for_inspection("Pagina #home cargada. Presiona Enter para listar atletas...")
        
        # =====================================================================
        # PASO 5: Obtener tiles de atletas
        # =====================================================================
        logger.info("=" * 60)
        logger.info("PASO 5: Obteniendo tiles de atletas")
        logger.info("=" * 60)
        
        tiles = athlete_service.get_athlete_tiles()
        logger.info(f"Total de tiles encontrados: {len(tiles)}")
        
        if not tiles:
            logger.error("No se encontraron tiles de atletas")
            return
        
        # Mostrar nombres de los primeros atletas
        logger.info("Primeros atletas encontrados:")
        for i, tile in enumerate(tiles[:5]):
            name = athlete_service.get_athlete_name_from_tile(tile)
            logger.info(f"  [{i}] {name}")
        
        if len(tiles) > 5:
            logger.info(f"  ... y {len(tiles) - 5} mas")
        
        pause_for_inspection("Tiles listados. Presiona Enter para hacer click en settings del primer atleta...")
        
        # =====================================================================
        # PASO 6: Click en settings del primer atleta
        # =====================================================================
        logger.info("=" * 60)
        logger.info("PASO 6: Click en boton de settings")
        logger.info("=" * 60)
        
        first_tile = tiles[0]
        first_name = athlete_service.get_athlete_name_from_tile(first_tile)
        logger.info(f"Haciendo click en settings de: {first_name}")
        
        success = athlete_service.click_athlete_settings_button(first_tile)
        
        if success:
            logger.info("Click en settings exitoso!")
            logger.info("El modal de settings deberia estar abierto ahora")
        else:
            logger.error("Fallo el click en settings")
        
        pause_for_inspection("Test completado. Presiona Enter para cerrar el navegador...")
        
    except Exception as e:
        logger.exception(f"Error durante el test: {e}")
        pause_for_inspection("Error detectado. Presiona Enter para cerrar...")
        
    finally:
        # =====================================================================
        # CLEANUP: Cerrar driver
        # =====================================================================
        if driver:
            logger.info("Cerrando driver...")
            driver.quit()
            logger.info("Driver cerrado")


if __name__ == "__main__":
    # Configurar logging para consola
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
    )
    
    logger.info("=" * 60)
    logger.info("TEST: Navegacion a #home y click en settings")
    logger.info("=" * 60)
    
    # Verificar credenciales
    if not os.getenv("TP_EMAIL") or not os.getenv("TP_PASSWORD"):
        logger.error("Variables TP_EMAIL y TP_PASSWORD no configuradas")
        logger.error("Configura las variables de entorno antes de ejecutar el test")
        sys.exit(1)
    
    run_test()
    
    logger.info("Test finalizado")
