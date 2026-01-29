"""
Servicio de gestion de Training Plans para TrainingPeaks.
Maneja la aplicacion de planes de entrenamiento a atletas en fechas especificas.
"""
import time
from datetime import date
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger


class TrainingPlanService:
    """
    Servicio de gestion de Training Plans para TrainingPeaks.
    Encapsula las operaciones para aplicar planes de entrenamiento a atletas.
    """
    
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """
        Inicializa el servicio de training plans.
        
        Args:
            driver: Instancia del WebDriver de Chrome
            wait: Instancia de WebDriverWait configurada
        """
        self._driver = driver
        self._wait = wait
    
    # =========================================================================
    # METODOS PARA NAVEGACION EN TRAINING PLANS LIBRARY
    # =========================================================================
    
    def click_training_plans_tab(self, timeout: int = 10) -> None:
        """
        Hace clic en la pestana "Training Plans" en el panel lateral.
        
        Args:
            timeout: Segundos de espera maxima
            
        Raises:
            TimeoutException: Si no se encuentra el elemento
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Buscar div.libraryTitle con texto "Training Plans"
        xpath = "//div[@class='libraryTitle' and text()='Training Plans']"
        
        training_plans_tab = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        training_plans_tab.click()
        logger.info("Click en pestana 'Training Plans'")
        
        # Esperar a que cargue el contenido
        time.sleep(0.5)
    
    def is_my_plans_expanded(self, timeout: int = 5) -> bool:
        """
        Verifica si la carpeta "My Plans" esta expandida.
        
        La carpeta esta expandida si el div.expander tiene la clase "expanded".
        
        Args:
            timeout: Segundos de espera maxima
            
        Returns:
            bool: True si esta expandida, False si no
        """
        try:
            # Buscar el folder que contiene "My Plans"
            xpath = (
                "//div[contains(@class, 'coachTrainingPlanLibraryFolder')]"
                "//span[@class='titleContain' and text()='My Plans']"
                "/ancestor::div[contains(@class, 'coachTrainingPlanLibraryFolder')]"
            )
            
            folder = WebDriverWait(self._driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            
            # Verificar si tiene clase "expanded"
            folder_classes = folder.get_attribute("class") or ""
            if "expanded" in folder_classes:
                return True
            
            # Verificar el expander interno
            try:
                expander = folder.find_element(By.CSS_SELECTOR, "div.expander")
                expander_classes = expander.get_attribute("class") or ""
                return "expanded" in expander_classes
            except NoSuchElementException:
                return False
                
        except TimeoutException:
            logger.warning("No se encontro la carpeta 'My Plans'")
            return False
    
    def expand_my_plans(self, timeout: int = 10) -> None:
        """
        Expande la carpeta "My Plans" si no esta expandida.
        
        Args:
            timeout: Segundos de espera maxima
        """
        if self.is_my_plans_expanded(timeout):
            logger.debug("'My Plans' ya esta expandida")
            return
        
        # Buscar el header de My Plans para hacer click
        xpath = (
            "//div[contains(@class, 'coachTrainingPlanLibraryFolder')]"
            "//span[@class='titleContain' and text()='My Plans']"
            "/ancestor::div[@class='toggleArea']"
        )
        
        try:
            toggle_area = WebDriverWait(self._driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            toggle_area.click()
            logger.info("Click para expandir 'My Plans'")
            time.sleep(0.5)
            
            # Verificar que se expandio
            if not self.is_my_plans_expanded(timeout):
                logger.warning("'My Plans' no se expandio despues del click")
        except TimeoutException:
            logger.error("No se pudo expandir 'My Plans'")
            raise
    
    def find_and_click_training_plan(self, plan_name: str, timeout: int = 10) -> None:
        """
        Busca un training plan por nombre y hace click en el.
        
        Args:
            plan_name: Nombre exacto del training plan
            timeout: Segundos de espera maxima
            
        Raises:
            TimeoutException: Si no se encuentra el plan
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Asegurar que My Plans este expandida
        self.expand_my_plans(timeout)
        
        # Buscar el tile del plan por el nombre en h3
        xpath = (
            f"//div[contains(@class, 'coachTrainingPlanLibraryTile')]"
            f"//h3[normalize-space(text())='{plan_name}']"
            f"/ancestor::div[contains(@class, 'coachTrainingPlanLibraryTile')]"
        )
        
        try:
            plan_tile = wait.until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            
            # Scroll al elemento
            self._driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                plan_tile
            )
            time.sleep(0.3)
            
            plan_tile.click()
            logger.info(f"Click en training plan: '{plan_name}'")
            
            # Esperar a que se abra el modal
            time.sleep(0.5)
            
        except TimeoutException:
            logger.error(f"No se encontro el training plan: '{plan_name}'")
            raise
    
    # =========================================================================
    # METODOS PARA EL MODAL DE TRAINING PLAN
    # =========================================================================
    
    def _wait_for_plan_modal(self, timeout: int = 10) -> bool:
        """
        Espera a que el modal del training plan este visible y listo.
        
        Args:
            timeout: Segundos de espera maxima
            
        Returns:
            bool: True si el modal esta visible
        """
        try:
            WebDriverWait(self._driver, timeout).until(
                EC.visibility_of_element_located((
                    By.CSS_SELECTOR, 
                    "div.tomahawkContent.trainingPlanDetails"
                ))
            )
            logger.debug("Modal tomahawkContent.trainingPlanDetails visible")
            # Pequena pausa para que el modal termine de renderizarse
            time.sleep(0.5)
            return True
        except TimeoutException:
            logger.warning("Modal del plan no aparecio")
            return False
    
    def click_select_athletes_button(self, timeout: int = 10) -> None:
        """
        Hace click en el boton "Select Athletes" para abrir el dropdown de atletas.
        
        Busca el boton dentro del modal tomahawkContent y espera a que el dropdown
        sea visible antes de continuar.
        
        Args:
            timeout: Segundos de espera maxima
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Buscar el boton "Select Athletes" dentro del modal tomahawkContent
        # Estructura: <button class="ui-multiselect ui-widget ui-state-default ui-corner-all">
        #               <span class="ui-icon ui-icon-triangle-1-s"></span>
        #               <span>Select Athletes</span>
        #             </button>
        xpath = (
            "//div[contains(@class, 'tomahawkContent')]"
            "//button[contains(@class, 'ui-multiselect')]"
            "[.//span[text()='Select Athletes']]"
        )
        
        select_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        
        # Scroll al elemento para asegurar visibilidad
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            select_btn
        )
        time.sleep(0.2)
        
        select_btn.click()
        logger.info("Click en boton 'Select Athletes'")
        
        # Esperar que el dropdown menu sea visible antes de continuar
        wait.until(
            EC.visibility_of_element_located((
                By.CSS_SELECTOR, 
                "div.ui-multiselect-menu"
            ))
        )
        logger.debug("Dropdown de atletas visible")
        time.sleep(0.3)
    
    def search_athlete_in_dropdown(self, athlete_name: str, timeout: int = 10) -> None:
        """
        Escribe el nombre del atleta en el campo de busqueda del dropdown.
        
        El input esta dentro de: <div class="ui-multiselect-filter">
        
        Args:
            athlete_name: Nombre del atleta a buscar
            timeout: Segundos de espera maxima
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Buscar el input de busqueda dentro del filtro del dropdown
        # Estructura: <div class="ui-multiselect-filter"><input placeholder="Search" type="search"></div>
        search_input = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR, 
                "div.ui-multiselect-filter input[type='search']"
            ))
        )
        
        # Click en el input para asegurar foco
        search_input.click()
        time.sleep(0.1)
        
        # Limpiar y escribir el nombre
        search_input.clear()
        search_input.send_keys(athlete_name)
        logger.info(f"Buscando atleta: '{athlete_name}'")
        
        # Esperar a que filtre los resultados
        time.sleep(0.5)
    
    def click_athlete_in_dropdown(self, athlete_name: str, timeout: int = 10) -> None:
        """
        Hace click en el atleta encontrado en el dropdown.
        
        El atleta visible tendra style="display: list-item;".
        
        Args:
            athlete_name: Nombre del atleta
            timeout: Segundos de espera maxima
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Buscar el li.nameSelect que contenga el nombre y este visible
        xpath = (
            f"//ul[contains(@class, 'ui-multiselect-checkboxes')]"
            f"//li[contains(@class, 'nameSelect')]"
            f"//span[normalize-space(text())='{athlete_name}']"
            f"/ancestor::li[contains(@class, 'nameSelect')]"
        )
        
        try:
            athlete_li = wait.until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            
            # Click en el label/checkbox
            athlete_li.click()
            logger.info(f"Atleta seleccionado: '{athlete_name}'")
            time.sleep(0.3)
            
        except TimeoutException:
            logger.error(f"No se encontro el atleta: '{athlete_name}'")
            raise
    
    def close_athlete_dropdown(self, timeout: int = 3) -> None:
        """
        Cierra el dropdown de atletas haciendo click en el boton Select Athletes.
        
        El boton tiene comportamiento toggle: click para abrir, click para cerrar.
        
        Args:
            timeout: Segundos de espera maxima
        """
        # Hacer click en el boton Select Athletes para cerrar el dropdown (toggle)
        try:
            xpath = (
                "//div[contains(@class, 'tomahawkContent')]"
                "//button[contains(@class, 'ui-multiselect')]"
                "[.//span[text()='Select Athletes']]"
            )
            
            select_btn = WebDriverWait(self._driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            select_btn.click()
            logger.debug("Dropdown de atletas cerrado (click en boton)")
            time.sleep(0.3)
        except Exception:
            # Si falla, usar Escape
            try:
                self._driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                logger.debug("Dropdown de atletas cerrado (Escape)")
            except Exception:
                pass
            time.sleep(0.3)
    
    def set_apply_date(self, target_date: date, timeout: int = 10) -> None:
        """
        Establece la fecha en el datepicker del modal.
        
        Usa JavaScript para establecer el valor de forma confiable
        independientemente del sistema operativo.
        
        Args:
            target_date: Fecha objetivo (objeto date)
            timeout: Segundos de espera maxima
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Formatear fecha para TrainingPeaks (M/D/YYYY)
        date_str = f"{target_date.month}/{target_date.day}/{target_date.year}"
        
        # Buscar el input del datepicker dentro del modal
        date_input = wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR, 
                "div.tomahawkContent input.datepicker.applyDate"
            ))
        )
        
        # Usar JavaScript para establecer el valor y disparar eventos
        self._driver.execute_script("""
            var input = arguments[0];
            var value = arguments[1];
            input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.blur();
        """, date_input, date_str)
        
        logger.info(f"Fecha establecida: {date_str}")
        time.sleep(0.5)
    
    def click_apply_button(self, timeout: int = 10) -> None:
        """
        Hace click en el boton "Apply" del modal de training plan.
        
        El boton esta en: <button class="apply tpSecondaryButton">Apply</button>
        
        Args:
            timeout: Segundos de espera maxima
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Buscar el boton Apply dentro del modal tomahawkContent
        xpath = (
            "//div[contains(@class, 'tomahawkContent')]"
            "//button[contains(@class, 'apply') and contains(@class, 'tpSecondaryButton')]"
        )
        
        apply_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        
        # Scroll al boton para asegurar visibilidad
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            apply_btn
        )
        time.sleep(0.2)
        
        # Usar JavaScript para el click (mas confiable)
        self._driver.execute_script("arguments[0].click();", apply_btn)
        logger.info("Click en boton 'Apply'")
        time.sleep(0.5)
    
    # =========================================================================
    # METODOS PARA MODALES DE CONFIRMACION
    # =========================================================================
    
    def confirm_apply_modal(self, timeout: int = 10) -> None:
        """
        Hace click en el boton "Apply" del modal de confirmacion.
        
        Este es el modal que aparece despues de hacer click en Apply inicial.
        
        Args:
            timeout: Segundos de espera maxima
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Buscar el boton con data-cy="primaryButton" y texto "Apply"
        xpath = "//button[@data-cy='primaryButton' and contains(text(), 'Apply')]"
        
        confirm_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        
        confirm_btn.click()
        logger.info("Click en boton 'Apply' de confirmacion")
        time.sleep(1)
    
    def click_ok_confirmation(self, timeout: int = 30) -> None:
        """
        Espera y hace click en el boton "OK" del modal final.
        
        Este boton aparece despues de que el plan se aplica exitosamente.
        Usa un timeout mayor porque la operacion puede tardar.
        
        Args:
            timeout: Segundos de espera maxima (default 30 para operaciones largas)
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Buscar el boton con data-cy="primaryButton" y texto "OK"
        xpath = "//button[@data-cy='primaryButton' and contains(text(), 'OK')]"
        
        ok_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        
        ok_btn.click()
        logger.info("Click en boton 'OK' - Plan aplicado exitosamente")
        time.sleep(0.5)
    
    # =========================================================================
    # METODO PRINCIPAL
    # =========================================================================
    
    def apply_training_plan(
        self, 
        plan_name: str, 
        athlete_name: str, 
        start_date: date,
        timeout: int = 10
    ) -> bool:
        """
        Aplica un training plan a un atleta en una fecha especifica.
        
        Flujo completo:
        1. Click en pestana Training Plans
        2. Expandir My Plans si es necesario
        3. Buscar y hacer click en el plan
        4. En el modal: seleccionar atleta
        5. Establecer fecha de inicio
        6. Click en Apply
        7. Confirmar en modal de confirmacion
        8. Click en OK final
        
        Args:
            plan_name: Nombre del training plan
            athlete_name: Nombre del atleta en TrainingPeaks
            start_date: Fecha de inicio del plan (objeto date)
            timeout: Segundos de espera por operacion
            
        Returns:
            bool: True si se aplico exitosamente
            
        Raises:
            TimeoutException: Si algun paso falla
        """
        logger.info(
            f"Aplicando plan '{plan_name}' a '{athlete_name}' "
            f"desde {start_date.isoformat()}"
        )
        
        try:
            # 1. Click en Training Plans tab
            self.click_training_plans_tab(timeout)
            
            # 2-3. Expandir My Plans y buscar el plan
            self.find_and_click_training_plan(plan_name, timeout)
            
            # Esperar que el modal este listo
            if not self._wait_for_plan_modal(timeout):
                raise TimeoutException("El modal del plan no se abrio")
            
            # 4. Seleccionar atleta
            self.click_select_athletes_button(timeout)
            self.search_athlete_in_dropdown(athlete_name, timeout)
            self.click_athlete_in_dropdown(athlete_name, timeout)
            self.close_athlete_dropdown()
            
            # 5. Establecer fecha
            self.set_apply_date(start_date, timeout)
            
            # 6. Click en Apply
            self.click_apply_button(timeout)
            
            # 7. Confirmar en modal
            self.confirm_apply_modal(timeout)
            
            # 8. Click en OK (con timeout mayor para esperar la operacion)
            self.click_ok_confirmation(timeout=30)
            
            logger.info(
                f"Plan '{plan_name}' aplicado exitosamente a '{athlete_name}'"
            )
            return True
            
        except TimeoutException as e:
            logger.error(f"Error aplicando training plan: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado aplicando training plan: {e}")
            raise
