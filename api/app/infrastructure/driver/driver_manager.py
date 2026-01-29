"""
Driver Manager - Gestion centralizada del WebDriver de Selenium.
Maneja el ciclo de vida del ChromeDriver para las sesiones de entrenamiento.

Configuracion de headless:
- SELENIUM_HEADLESS=true: Modo headless (produccion, sin GUI)
- SELENIUM_HEADLESS=false: Modo con GUI (desarrollo, para debugging)
"""
from typing import Optional, Dict
from datetime import datetime
import uuid

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from loguru import logger

from app.core.config import settings
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService
from app.infrastructure.driver.services.workout_service import WorkoutService
from app.infrastructure.driver.services.training_plan_service import TrainingPlanService


# URLs de TrainingPeaks
TRAININGPEAKS_URL = "https://app.trainingpeaks.com/#calendar"
TRAININGPEAKS_HOME_URL = "https://app.trainingpeaks.com/#home"


class DriverSession:
    """
    Representa una sesion activa de un driver de Selenium.
    Contiene el driver, los servicios y metadatos de la sesion.
    """
    
    def __init__(
        self, 
        session_id: str, 
        athlete_name: str, 
        driver: webdriver.Chrome,
        wait: WebDriverWait
    ):
        """
        Inicializa una sesion de driver con sus servicios.
        
        Args:
            session_id: Identificador unico de la sesion
            athlete_name: Nombre del atleta asociado
            driver: Instancia del WebDriver de Chrome
            wait: Instancia de WebDriverWait configurada
        """
        self.session_id = session_id
        self.athlete_name = athlete_name
        self.driver = driver
        self.wait = wait
        self.created_at = datetime.now()
        self.is_active = True
        
        # Inicializar servicios para esta sesion
        self.auth_service = AuthService(driver, wait)
        self.athlete_service = AthleteService(driver, wait)
        self.workout_service = WorkoutService(driver, wait)
        self.training_plan_service = TrainingPlanService(driver, wait)
    
    def close(self) -> None:
        """Cierra el driver y marca la sesion como inactiva."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info(f"Driver cerrado para sesion {self.session_id}")
            except Exception as e:
                logger.error(f"Error al cerrar driver: {e}")
        self.is_active = False


class DriverManager:
    """
    Gestor centralizado de drivers de Selenium.
    Permite crear, obtener y cerrar sesiones de driver por atleta.
    """
    
    # Almacenamiento de sesiones activas (en memoria)
    _sessions: Dict[str, DriverSession] = {}
    
    @classmethod
    def create_session(cls, athlete_name: str, session_id: Optional[str] = None) -> DriverSession:
        """
        Crea una nueva sesion de driver para un atleta.
        
        Si ya existe una sesion activa para el atleta, la cierra primero.
        
        Args:
            athlete_name: Nombre del atleta
            session_id: ID de sesion opcional. Si no se provee, se genera uno nuevo.
            
        Returns:
            DriverSession: La sesion creada con el driver activo
        """
        # Si existe una sesion previa para este atleta, cerrarla
        existing_session = cls.get_session_by_athlete(athlete_name)
        if existing_session:
            logger.info(f"Cerrando sesion existente para atleta: {athlete_name}")
            cls.close_session(existing_session.session_id)
        
        # Crear nuevo driver
        if not session_id:
            session_id = str(uuid.uuid4())
            
        driver, wait = cls._create_driver()
        
        # Crear sesion
        session = DriverSession(
            session_id=session_id,
            athlete_name=athlete_name,
            driver=driver,
            wait=wait
        )
        
        cls._sessions[session_id] = session
        logger.info(f"Sesion creada: {session_id} para atleta: {athlete_name}")
        
        return session
    
    @classmethod
    def _create_driver(cls) -> tuple[webdriver.Chrome, WebDriverWait]:
        """
        Crea e inicializa un nuevo WebDriver de Chrome.
        Abre la pagina de TrainingPeaks automaticamente.
        
        El modo headless se controla via settings.SELENIUM_HEADLESS:
        - True (default): Modo headless para produccion/servidor
        - False: Modo con GUI para desarrollo/debugging
        
        Returns:
            tuple: (WebDriver, WebDriverWait)
        """
        opts = Options()
        
        # Modo headless configurable via SELENIUM_HEADLESS
        if settings.SELENIUM_HEADLESS:
            opts.add_argument("--headless=new")
            logger.info("Chrome iniciando en modo headless")
        else:
            logger.info("Chrome iniciando con GUI (desarrollo)")
        
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--remote-debugging-port=9222")
        
        driver = webdriver.Chrome(options=opts)
        wait = WebDriverWait(driver, 10)
        
        # Abrir TrainingPeaks
        driver.get(TRAININGPEAKS_URL)
        logger.info(f"Navegador abierto en: {TRAININGPEAKS_URL}")
        
        return driver, wait
    
    @classmethod
    def _create_driver_for_home(cls) -> tuple[webdriver.Chrome, WebDriverWait]:
        """
        Crea e inicializa un nuevo WebDriver de Chrome navegando a #home.
        
        Similar a _create_driver() pero navega a la pagina de inicio (#home)
        en lugar del calendario. Util para operaciones que requieren acceso
        a la lista de atletas sin seleccionar uno especifico.
        
        Returns:
            tuple: (WebDriver, WebDriverWait)
        """
        opts = Options()
        
        if settings.SELENIUM_HEADLESS:
            opts.add_argument("--headless=new")
            logger.info("Chrome iniciando en modo headless (home)")
        else:
            logger.info("Chrome iniciando con GUI para #home")
        
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--disable-infobars")
        opts.add_argument("--remote-debugging-port=9222")
        
        driver = webdriver.Chrome(options=opts)
        wait = WebDriverWait(driver, 10)
        
        # Abrir TrainingPeaks Home
        driver.get(TRAININGPEAKS_HOME_URL)
        logger.info(f"Navegador abierto en: {TRAININGPEAKS_HOME_URL}")
        
        return driver, wait
    
    @classmethod
    def initialize_training_session(cls, athlete_name: str, session_id: Optional[str] = None) -> "DriverSession":
        """
        Inicializa una sesion completa de entrenamiento (sincrono).
        
        Realiza el flujo completo:
        1. Crea el driver y abre TrainingPeaks
        2. Hace login con cookies
        3. Selecciona el atleta
        4. Abre la Workout Library
        
        NOTA: Esta version es sincrona y bloquea el event loop.
        Para uso en contextos async, usar initialize_training_session_async().
        
        Args:
            athlete_name: Nombre del atleta a seleccionar
            
        Returns:
            DriverSession: La sesion inicializada y lista para usar
        """
        # Crear sesion basica
        session = cls.create_session(athlete_name, session_id)
        
        try:
            # Login en TrainingPeaks
            logger.info("Iniciando login en TrainingPeaks...")
            session.auth_service.login_with_cookie()
            
            # Seleccionar atleta
            logger.info(f"Seleccionando atleta: {athlete_name}...")
            session.athlete_service.select_athlete(athlete_name)
            
            # Abrir Workout Library
            logger.info("Abriendo Workout Library...")
            session.workout_service.workout_library()
            
            logger.info(f"Sesion de entrenamiento inicializada para: {athlete_name}")
            return session
            
        except Exception as e:
            # Better error logging with full exception details
            import traceback
            error_msg = str(e) if str(e) else f"Exception type: {type(e).__name__}"
            logger.error(f"Error durante inicializacion de sesion: {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Cerrar sesion en caso de error
            cls.close_session(session.session_id)
            raise
    
    @classmethod
    async def initialize_training_session_async(cls, athlete_name: str, session_id: Optional[str] = None) -> "DriverSession":
        """
        Inicializa una sesion completa de entrenamiento (asincrono, no bloquea).
        
        Version async que ejecuta las operaciones de Selenium en threads separados
        via run_selenium() para no bloquear el event loop. Esto permite que el
        healthcheck y otras requests respondan durante la inicializacion.
        
        Realiza el flujo completo:
        1. Crea el driver y abre TrainingPeaks (en thread)
        2. Hace login con cookies (en thread)
        3. Selecciona el atleta (en thread)
        4. Abre la Workout Library (en thread)
        
        Args:
            athlete_name: Nombre del atleta a seleccionar
            session_id: ID de sesion opcional
            
        Returns:
            DriverSession: La sesion inicializada y lista para usar
        """
        from app.infrastructure.driver.selenium_executor import run_selenium
        
        # Crear sesion basica en thread (incluye crear driver)
        session = await run_selenium(cls.create_session, athlete_name, session_id)
        
        try:
            # Login en TrainingPeaks (en thread)
            logger.info("Iniciando login en TrainingPeaks (async)...")
            await run_selenium(session.auth_service.login_with_cookie)
            
            # Seleccionar atleta (en thread)
            logger.info(f"Seleccionando atleta: {athlete_name} (async)...")
            await run_selenium(session.athlete_service.select_athlete, athlete_name)
            
            # Abrir Workout Library (en thread)
            logger.info("Abriendo Workout Library (async)...")
            await run_selenium(session.workout_service.workout_library)
            
            logger.info(f"Sesion de entrenamiento inicializada (async) para: {athlete_name}")
            return session
            
        except Exception as e:
            import traceback
            error_msg = str(e) if str(e) else f"Exception type: {type(e).__name__}"
            logger.error(f"Error durante inicializacion de sesion (async): {error_msg}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Cerrar sesion en caso de error
            cls.close_session(session.session_id)
            raise
    
    @classmethod
    def get_session(cls, session_id: str) -> Optional[DriverSession]:
        """
        Obtiene una sesion por su ID.
        
        Args:
            session_id: ID de la sesion a buscar
            
        Returns:
            DriverSession o None si no existe
        """
        return cls._sessions.get(session_id)
    
    @classmethod
    def get_session_by_athlete(cls, athlete_name: str) -> Optional[DriverSession]:
        """
        Obtiene la sesion activa de un atleta.
        
        Args:
            athlete_name: Nombre del atleta
            
        Returns:
            DriverSession o None si no existe
        """
        for session in cls._sessions.values():
            if session.athlete_name == athlete_name and session.is_active:
                return session
        return None
    
    @classmethod
    def close_session(cls, session_id: str) -> bool:
        """
        Cierra una sesion y libera sus recursos.
        
        Args:
            session_id: ID de la sesion a cerrar
            
        Returns:
            bool: True si se cerro correctamente, False si no existia
        """
        session = cls._sessions.pop(session_id, None)
        if session:
            session.close()
            return True
        return False
    
    @classmethod
    def close_all_sessions(cls) -> int:
        """
        Cierra todas las sesiones activas.
        Util para limpieza al cerrar la aplicacion.
        
        Returns:
            int: Numero de sesiones cerradas
        """
        count = 0
        for session_id in list(cls._sessions.keys()):
            if cls.close_session(session_id):
                count += 1
        logger.info(f"Se cerraron {count} sesiones de driver")
        return count
    
    @classmethod
    def is_session_active(cls, session_id: str) -> bool:
        """
        Verifica si una sesion esta activa.
        
        Args:
            session_id: ID de la sesion a verificar
            
        Returns:
            bool: True si la sesion existe y esta activa
        """
        session = cls.get_session(session_id)
        if not session:
            return False
        
        # Verificar que el driver sigue respondiendo
        try:
            _ = session.driver.current_url
            return session.is_active
        except Exception:
            # Si el driver no responde, marcar como inactivo
            session.is_active = False
            return False

