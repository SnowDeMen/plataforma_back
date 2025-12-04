"""
Servicio de autenticacion para TrainingPeaks.
Maneja el login y el cierre del banner de cookies.
"""
import os
import dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

# Cargar variables de entorno
dotenv.load_dotenv()


class AuthService:
    """
    Servicio de autenticacion para TrainingPeaks.
    Encapsula las operaciones de login y manejo de cookies.
    """
    
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """
        Inicializa el servicio de autenticacion.
        
        Args:
            driver: Instancia del WebDriver de Chrome
            wait: Instancia de WebDriverWait configurada
        """
        self._driver = driver
        self._wait = wait
    
    def login(self) -> None:
        """
        Realiza el login en TrainingPeaks.
        Usa las credenciales de las variables de entorno USER y PASSWORD.
        """
        user = self._wait.until(EC.element_to_be_clickable((By.NAME, "Username")))
        user.click()
        user.send_keys(os.getenv("USER"))
        passw = self._wait.until(EC.element_to_be_clickable((By.NAME, "Password")))
        passw.click()
        passw.send_keys(os.getenv("PASSWORD"))
        login_button = self._wait.until(EC.element_to_be_clickable((By.ID, "btnSubmit")))
        login_button.click()
        logger.info("Login realizado en TrainingPeaks")
    
    def close_cookie_banner(self) -> None:
        """
        Cierra el banner de cookies de OneTrust si esta presente.
        Se recomienda llamarla justo despues de cargar la pagina y antes del login.
        """
        try:
            banner_btn = self._wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "onetrust-close-btn-handler"))
            )
            self._driver.execute_script("arguments[0].click();", banner_btn)
            logger.info("Cookie banner cerrado correctamente")
        except Exception:
            logger.debug("No se encontro el banner de cookies (posiblemente ya cerrado)")
    
    def login_with_cookie(self) -> None:
        """
        Realiza el flujo completo de login.
        Primero cierra el banner de cookies y luego hace login.
        """
        self.close_cookie_banner()
        self.login()

