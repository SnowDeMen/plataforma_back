"""
Servicio de gestion de atletas para TrainingPeaks.
Maneja la seleccion y navegacion en la biblioteca de atletas.
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger


class AthleteService:
    """
    Servicio de gestion de atletas para TrainingPeaks.
    Encapsula las operaciones de navegacion y seleccion de atletas.
    """
    
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """
        Inicializa el servicio de atletas.
        
        Args:
            driver: Instancia del WebDriver de Chrome
            wait: Instancia de WebDriverWait configurada
        """
        self._driver = driver
        self._wait = wait
    
    def is_athlete_library_open(self, timeout: int = 5) -> bool:
        """
        Verifica si la pestana 'Athlete Library' esta abierta (activa).

        Args:
            timeout: Segundos de espera maxima
            
        Returns:
            True si la clase del elemento contiene 'active',
            False si no esta activa o si no se encuentra el elemento.
        """
        try:
            element = WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located((By.ID, "athleteLibrary"))
            )
            classes = element.get_attribute("class") or ""
            if "active" in classes.split():
                return True
            else:
                return False
        except Exception as e:
            logger.debug(f"No se pudo determinar el estado de 'Athlete Library': {e}")
            return False
    
    def click_athlete_library(self, timeout: int = 10) -> None:
        """
        Hace clic en el boton 'Athlete Library' (independientemente de si esta abierto o cerrado).
        
        Args:
            timeout: Segundos de espera maxima
        """
        try:
            athlete_btn = WebDriverWait(self._driver, timeout).until(
                EC.element_to_be_clickable((By.ID, "athleteLibrary"))
            )
            athlete_btn.click()
            logger.info("Se hizo clic en 'Athlete Library'")
        except Exception as e:
            logger.error(f"No se pudo hacer clic en 'Athlete Library': {e}")
    
    def athlete_library(self, timeout: int = 10) -> None:
        """
        Asegura que estas en el panel de Athlete Library.
        Si no esta activo, hace click en la pestana correspondiente.
        
        Args:
            timeout: Segundos de espera maxima
            
        Raises:
            TimeoutException: Si no se puede abrir Athlete Library
        """
        if not self.is_athlete_library_open():
            self.click_athlete_library()

        if not self.is_athlete_library_open():
            raise TimeoutException("Athlete Library no quedo activa tras el intento de apertura.")
    
    def _is_folder_expanded(self, folder_root) -> bool:
        """
        Detecta si una carpeta de atletas ya esta expandida.
        Usa heuristicas de clase y atributos.
        
        Args:
            folder_root: Elemento WebElement de la carpeta
            
        Returns:
            bool: True si esta expandida
        """
        try:
            cls = (folder_root.get_attribute("class") or "").lower()
            if "expanded" in cls:
                return True

            header = folder_root.find_element(By.CSS_SELECTOR, ".coachAthleteLibraryFolderNameContainer")
            aria = (header.get_attribute("aria-expanded") or "").lower()
            if aria == "true":
                return True

            arrow = folder_root.find_element(By.CSS_SELECTOR, ".coachAthleteLibraryFolderArrowIcon")
            arrow_cls = (arrow.get_attribute("class") or "").lower()
            if "open" in arrow_cls or "expanded" in arrow_cls:
                return True

            possible_lists = [
                ".athleteTiles", "[data_cy='athleteTiles']",
                ".athletesList", ".athleteCards", ".itemsContainer"
            ]
            for sel in possible_lists:
                try:
                    el = folder_root.find_element(By.CSS_SELECTOR, sel)
                    if el.is_displayed():
                        return True
                except NoSuchElementException:
                    continue

            return False
        except Exception:
            return False
    
    def expand_all_athlete_libraries(self, timeout: int = 10, wait_between_clicks: float = 0.15) -> int:
        """
        Expande todas las carpetas de atletas en la vista de libreria.
        Usa clicks normales, sin JS ni Actions.

        Args:
            timeout: Segundos de espera maxima
            wait_between_clicks: Tiempo de espera entre clicks
            
        Returns:
            int: Numero de carpetas que se expandieron efectivamente
        """
        wait = WebDriverWait(self._driver, timeout)

        container = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data_cy='athletesContainer']"))
        )

        folders = container.find_elements(By.CSS_SELECTOR, "[data_cy='coachAthleteLibraryFolder']")

        expanded_count = 0
        for folder in folders:
            try:
                header = folder.find_element(By.CSS_SELECTOR, ".coachAthleteLibraryFolderNameContainer")

                if self._is_folder_expanded(folder):
                    continue

                self._driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", header)
                time.sleep(0.1)

                header.click()
                time.sleep(wait_between_clicks)

                if self._is_folder_expanded(folder):
                    expanded_count += 1

            except Exception:
                continue

        return expanded_count
    
    def _xpath_literal(self, s: str) -> str:
        """
        Convierte un string Python a un literal XPath seguro.
        
        Args:
            s: String a convertir
            
        Returns:
            str: Literal XPath seguro
        """
        if "'" not in s:
            return f"'{s}'"
        if '"' not in s:
            return f'"{s}"'
        parts = []
        for part in s.split("'"):
            parts.append(f"'{part}'")
            parts.append('"\'"')
        parts = parts[:-1]
        return f"concat({', '.join(parts)})"
    
    def click_athlete_by_name(self, name: str, timeout: int = 10) -> None:
        """
        Da clic a la tarjeta del atleta cuyo span coincide exactamente con 'name'.
        
        Args:
            name: Nombre exacto del atleta
            timeout: Segundos de espera maxima
        """
        wait = WebDriverWait(self._driver, timeout)
        self.expand_all_athlete_libraries()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data_cy='itemsContainer']")))
        name_literal = self._xpath_literal(name.strip())

        xpath = (
            "//div[@data_cy='athleteTileName']"
            f"/span[normalize-space(text()) = {name_literal}]"
            "/ancestor::div[contains(@class,'athleteTile')]"
        )

        tile = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        tile.click()
        logger.info(f"Atleta '{name}' seleccionado")
    
    def select_athlete(self, name: str, timeout: int = 5) -> None:
        """
        Realiza el flujo completo de seleccion de un atleta con estrategia de reintentos.
        Intenta varias combinaciones de nombre si la busqueda exacta falla.
        
        Order of attempts:
        1. Full exact name
        2. First Name + First Last Name
        3. First Name + Last Last Name (if different)
        4. First Name only
        
        Args:
            name: Nombre del atleta
            timeout: Segundos de espera por intento
            
        Raises:
             AthleteNotFoundInTPException: Si no se encuentra despues de todos los intentos
        """
        from app.shared.exceptions.domain import AthleteNotFoundInTPException
        
        self.click_athlete_library()
        self.expand_all_athlete_libraries()
        
        # Generate variations
        variations = [name]
        parts = name.split()
        
        if len(parts) > 2:
            # First + First Last (e.g., "Abiezer Davila" from "Abiezer Davila Rivera")
            v2 = f"{parts[0]} {parts[1]}"
            if v2 not in variations:
                variations.append(v2)
                
            # First + Last Last (e.g., "Abiezer Rivera")
            v3 = f"{parts[0]} {parts[-1]}"
            if v3 not in variations:
                variations.append(v3)
        
        if len(parts) > 1:
            # First Name only
            v4 = parts[0]
            if v4 not in variations:
                variations.append(v4)
                
            # Last Name only (common in some lists if sorted by last name? No, risky. Let's stick to first name)
            
        logger.info(f"Intentando seleccionar atleta '{name}' con variaciones: {variations}")
        
        for variation in variations:
            try:
                logger.debug(f"Buscando atleta: '{variation}'")
                self.click_athlete_by_name(variation, timeout=timeout)
                logger.info(f"Atleta encontrado y seleccionado como: '{variation}'")
                return
            except TimeoutException:
                logger.warning(f"No se encontro atleta con nombre: '{variation}'")
                continue
                
        # If we get here, all attempts failed
        logger.error(f"Fallo la seleccion de atleta para: {name}. Intentos: {variations}")
        raise AthleteNotFoundInTPException(name, variations)

