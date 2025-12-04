"""
Servicio de gestion de Workout Library para TrainingPeaks.
Maneja la apertura y navegacion en la biblioteca de entrenamientos.
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from loguru import logger


class WorkoutService:
    """
    Servicio de gestion de Workout Library para TrainingPeaks.
    Encapsula las operaciones de navegacion en la biblioteca de entrenamientos.
    """
    
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """
        Inicializa el servicio de workout library.
        
        Args:
            driver: Instancia del WebDriver de Chrome
            wait: Instancia de WebDriverWait configurada
        """
        self._driver = driver
        self._wait = wait
    
    def click_workout_library(self) -> None:
        """
        Hace clic en el boton de Workout Library para abrir el slider.
        """
        workout_library_button = self._wait.until(
            EC.element_to_be_clickable((By.ID, "exerciseLibrary"))
        )
        workout_library_button.click()
        logger.info("Se hizo clic en 'Workout Library'")
    
    def is_workout_library_open(self, timeout: int = 0, visible_only: bool = True) -> bool:
        """
        Verifica si la Workout Library esta abierta.
        
        Args:
            timeout: Segundos para esperar (0 = chequeo inmediato)
            visible_only: Si True, exige que al menos un componente este visible
            
        Returns:
            True si existe (y opcionalmente visible) un workoutLibraryMainComponent,
            False si no existe o no visible.
        """
        selector = ".activeLibraryContainer .workoutLibraryMainComponent[data_cy='workoutLibraryContainer']"
        try:
            if timeout and timeout > 0:
                root = WebDriverWait(self._driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return (root.is_displayed() if visible_only else True)
            else:
                els = self._driver.find_elements(By.CSS_SELECTOR, selector)
                if not els:
                    return False
                return any(e.is_displayed() for e in els) if visible_only else True
        except Exception:
            return False
    
    def workout_library(self) -> None:
        """
        Asegura que estas en el panel de Workout Library.
        Si no esta activo, hace click en la pestana correspondiente.
        
        Raises:
            TimeoutException: Si no se puede abrir el panel de Workout Library
        """
        if not self.is_workout_library_open():
            self.click_workout_library()
        
        if not self.is_workout_library_open():
            raise TimeoutException("No se pudo abrir el panel de Workout Library.")
        
        logger.info("Workout Library abierta correctamente")

