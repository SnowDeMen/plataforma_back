"""
Servicio de gestion de atletas para TrainingPeaks.
Maneja la seleccion y navegacion en la biblioteca de atletas.
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from loguru import logger
from typing import Optional


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
    
    def is_athlete_library_open(self, timeout: int = 10) -> bool:
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
        Incluye scroll al elemento, fallback a JavaScript click, y verificacion
        post-click para confirmar que la seleccion ocurrio.
        
        Args:
            name: Nombre exacto del atleta
            timeout: Segundos de espera maxima
            
        Raises:
            AthleteNotFoundInTPException: Si el atleta no se encuentra o la seleccion
                                          no se verifica correctamente
        """
        from app.shared.exceptions.domain import AthleteNotFoundInTPException
        
        wait = WebDriverWait(self._driver, timeout)
        self.expand_all_athlete_libraries()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data_cy='itemsContainer']")))
        name_literal = self._xpath_literal(name.strip())

        # Usar contains para matchear 'athleteTile cf', excluyendo 'athleteTileNameContainer'
        xpath = (
            "//div[@data_cy='athleteTileName']"
            f"/span[normalize-space(text()) = {name_literal}]"
            "/ancestor::div[contains(@class,'athleteTile') and not(contains(@class,'Container'))]"
        )

        tile = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        
        # 1. Scroll al elemento para asegurar visibilidad
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", 
            tile
        )
        time.sleep(0.3)
        
        # 2. Log del elemento encontrado
        logger.info(
            f"Tile encontrado para '{name}': "
            f"visible={tile.is_displayed()}, enabled={tile.is_enabled()}"
        )
        
        # 3. Verificar si el atleta YA esta seleccionado (evita click innecesario)
        current_selected = self._get_selected_athlete_name()
        if current_selected and self._names_match(current_selected, name):
            logger.info(f"Atleta '{name}' ya estaba seleccionado (actual: '{current_selected}')")
            return
        
        logger.debug(f"Atleta actual: '{current_selected}', cambiando a '{name}'")
        
        # 4. Intentar click normal, si falla usar JavaScript click
        try:
            tile.click()
            logger.debug(f"Click normal ejecutado en tile de '{name}'")
        except Exception as e:
            logger.warning(f"Click normal fallo: {e}. Intentando JavaScript click...")
            self._driver.execute_script("arguments[0].click();", tile)
            logger.debug(f"JavaScript click ejecutado en tile de '{name}'")
        
        # 5. Esperar con polling hasta que el atleta cambie al esperado (max 5s)
        if not self._wait_for_athlete_selection(name, timeout=10):
            logger.error(f"Verificacion de seleccion fallo para '{name}'")
            raise AthleteNotFoundInTPException(name, [name])
        
        logger.info(f"Atleta '{name}' seleccionado y verificado")
    
    def _get_selected_athlete_name(self) -> str:
        """
        Obtiene el nombre del atleta actualmente seleccionado.
        
        Busca en el elemento .selectedAthleteName span que muestra
        el nombre del atleta seleccionado en TrainingPeaks.
        
        Returns:
            str: Nombre del atleta seleccionado, o string vacio si no se encuentra
        """
        try:
            selected_element = self._driver.find_element(
                By.CSS_SELECTOR, 
                "div.selectedAthleteName span"
            )
            return selected_element.text.strip()
        except NoSuchElementException:
            return ""
        except Exception as e:
            logger.debug(f"Error obteniendo nombre seleccionado: {e}")
            return ""
    
    def _wait_for_athlete_selection(self, expected_name: str, timeout: int = 10) -> bool:
        """
        Espera con polling hasta que el atleta seleccionado coincida con el esperado.
        
        Hace polling cada 0.1 segundos hasta que el nombre en .selectedAthleteName
        coincida con expected_name, o hasta que se agote el timeout.
        
        Args:
            expected_name: Nombre esperado del atleta
            timeout: Segundos maximos de espera
            
        Returns:
            bool: True si el atleta esperado fue seleccionado, False si timeout
        """
        max_attempts = timeout * 10  # 10 intentos por segundo
        
        for attempt in range(max_attempts):
            actual_name = self._get_selected_athlete_name()
            
            if actual_name and self._names_match(actual_name, expected_name):
                logger.info(
                    f"Verificacion OK (intento {attempt + 1}): "
                    f"'{actual_name}' coincide con '{expected_name}'"
                )
                return True
            
            time.sleep(0.1)
        
        # Timeout - mostrar el nombre actual para debug
        final_name = self._get_selected_athlete_name()
        logger.warning(
            f"Timeout esperando seleccion: actual='{final_name}', "
            f"esperado='{expected_name}' (despues de {timeout}s)"
        )
        return False
    
    def _verify_athlete_selected(self, expected_name: str, timeout: int = 10) -> bool:
        """
        Verifica que el atleta fue seleccionado correctamente.
        
        Wrapper para compatibilidad. Usa _wait_for_athlete_selection internamente.
        
        Args:
            expected_name: Nombre esperado del atleta
            timeout: Segundos de espera maxima
            
        Returns:
            bool: True si el nombre coincide, False si no
        """
        return self._wait_for_athlete_selection(expected_name, timeout)
    
    def select_athlete(self, name: str, timeout: int = 10) -> None:
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
    
    # =========================================================================
    # METODOS PARA BUSQUEDA POR USERNAME (Pagina #home)
    # =========================================================================
    
    def navigate_to_home(self, timeout: int = 15) -> None:
        """
        Navega a la pagina #home de TrainingPeaks donde se muestra la lista
        de atletas con sus tiles. Esta pagina permite acceder a la configuracion
        de cada atleta para obtener su username.
        
        Args:
            timeout: Segundos de espera maxima para cargar la pagina
            
        Raises:
            TimeoutException: Si la pagina no carga correctamente
        """
        from app.infrastructure.driver.driver_manager import TRAININGPEAKS_HOME_URL
        
        current_url = self._driver.current_url
        
        # Navegar solo si no estamos ya en #home
        if "#home" not in current_url:
            logger.info(f"Navegando a TrainingPeaks Home: {TRAININGPEAKS_HOME_URL}")
            self._driver.get(TRAININGPEAKS_HOME_URL)
        else:
            logger.debug("Ya estamos en la pagina #home")
        
        # Esperar a que cargue el contenedor de atletas (pagina #home)
        wait = WebDriverWait(self._driver, timeout)
        try:
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".athleteListAthletes"))
            )
            logger.info("Pagina #home cargada correctamente")
        except TimeoutException:
            logger.error("Timeout esperando que cargue la pagina #home")
            raise
    
    def get_athlete_tiles(self, timeout: int = 10) -> list:
        """
        Obtiene todos los tiles de atletas visibles en la pagina #home.
        
        En la pagina #home, cada atleta se representa como un div.athleteCoachHome
        dentro del contenedor .athleteListAthletes.
        
        Args:
            timeout: Segundos de espera maxima
            
        Returns:
            list: Lista de WebElements correspondientes a cada tile de atleta
        """
        wait = WebDriverWait(self._driver, timeout)
        
        # Esperar a que aparezca el contenedor de atletas
        try:
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".athleteListAthletes"))
            )
        except TimeoutException:
            logger.warning("No se encontro contenedor de lista de atletas")
            return []
        
        # Obtener todos los tiles de atletas (estructura de pagina #home)
        tiles = self._driver.find_elements(
            By.CSS_SELECTOR, 
            ".athleteListAthletes .athleteCoachHome"
        )
        
        logger.info(f"Se encontraron {len(tiles)} tiles de atletas")
        return tiles
    
    def click_athlete_settings_button(self, athlete_tile, timeout: int = 10) -> bool:
        """
        Hace click en el boton de settings de un tile de atleta especifico.
        Este boton abre el modal de configuracion donde se puede ver el username.
        
        En la pagina #home, el boton de settings esta dentro de un div con
        aria-label="Go to this athlete's settings" que contiene un button.
        
        Args:
            athlete_tile: WebElement del tile del atleta
            timeout: Segundos de espera maxima
            
        Returns:
            bool: True si se hizo click exitosamente, False en caso contrario
        """
        # Hacer scroll al tile para asegurar visibilidad
        self._driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", 
            athlete_tile
        )
        
        # Simular hover sobre el tile para mostrar el boton si es necesario
        try:
            actions = ActionChains(self._driver)
            actions.move_to_element(athlete_tile).perform()
            time.sleep(0.2) # Esperar animacion hover
        except Exception as e:
            logger.warning(f"No se pudo hacer hover sobre el tile: {e}")
        
        time.sleep(0.3)
        
        settings_btn = None
        
        # Estrategia 1: Buscar el button dentro del div con aria-label (estructura de #home)
        try:
            settings_btn = athlete_tile.find_element(
                By.CSS_SELECTOR, 
                'div[aria-label="Go to this athlete\'s settings"] button'
            )
            # Intentar encontrarlo aunque is_displayed sea falso inicialmente
            if settings_btn:
                logger.debug("Boton de settings encontrado via div[aria-label] button")
        except NoSuchElementException:
            pass
        
        # Estrategia 2: Buscar button con SettingsIcon
        if not settings_btn:
            try:
                settings_btn = athlete_tile.find_element(
                    By.CSS_SELECTOR, 
                    'button [data-testid="SettingsIcon"]'
                )
                # Obtener el button padre
                settings_btn = settings_btn.find_element(By.XPATH, '..')
                if settings_btn:
                    logger.debug("Boton de settings encontrado via SettingsIcon")
            except NoSuchElementException:
                pass
        
        if not settings_btn:
            logger.warning("No se encontro el boton de settings en el tile")
            return False
        
        
        # Lista de estrategias de interaccion para probar en orden
        strategies = [
            ("Keyboard ENTER", lambda btn: (self._driver.execute_script("arguments[0].focus();", btn), btn.send_keys(Keys.ENTER))),
            ("ActionChains Click", lambda btn: ActionChains(self._driver).move_to_element(btn).pause(0.2).click().perform()),
            ("JS Click", lambda btn: self._driver.execute_script("arguments[0].click();", btn)),
            ("JS Dispatch", lambda btn: self._driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {view: window, bubbles: true, cancelable: true}));", btn))
        ]
        
        for name, strategy in strategies:
            try:
                # Intentar estrategia
                strategy(settings_btn)
                logger.debug(f"Estrategia ejecutada: {name}")
                
                # Verificar si el modal se abrio (aumentado a 10s porque puede ser lento)
                try:
                    WebDriverWait(self._driver, 10.0).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".fieldContain"))
                    )
                    logger.info(f"Modal abierto exitosamente con estrategia: {name}")
                    return True
                except TimeoutException:
                    logger.debug(f"Estrategia {name} no abrio el modal en 5s, reintentando...")
                    
            except Exception as e:
                logger.warning(f"Error en estrategia {name}: {e}")
                
        logger.error("Todas las estrategias para clickear settings fallaron")
        return False
    
    def get_athlete_name_from_tile(self, athlete_tile) -> str:
        """
        Extrae el nombre visible del atleta desde su tile.
        
        En la pagina #home, el nombre esta en el atributo aria-label del div
        .athleteProfileAndName o en el texto del elemento p.MuiTypography-body2.
        
        Args:
            athlete_tile: WebElement del tile del atleta
            
        Returns:
            str: Nombre del atleta o string vacio si no se encuentra
        """
        # Estrategia 1: Obtener del aria-label del contenedor de perfil
        try:
            profile_div = athlete_tile.find_element(
                By.CSS_SELECTOR, 
                ".athleteProfileAndName"
            )
            name = profile_div.get_attribute("aria-label")
            if name:
                return name.strip()
        except NoSuchElementException:
            pass
        
        # Estrategia 2: Obtener del texto del elemento Typography
        try:
            name_element = athlete_tile.find_element(
                By.CSS_SELECTOR, 
                "p.MuiTypography-body2"
            )
            name = name_element.text.strip()
            if name:
                return name
        except NoSuchElementException:
            pass
        
        logger.warning("No se pudo extraer el nombre del tile")
        return ""
    
    # =========================================================================
    # METODOS PARA MODAL DE SETTINGS
    # =========================================================================
    
    def wait_for_settings_modal(self, timeout: int = 10) -> bool:
        """
        Espera a que el modal de settings del atleta se abra completamente.
        
        El modal contiene campos como Username, First and Last Name, etc.
        Se detecta esperando la presencia de elementos con clase fieldContain.
        
        Args:
            timeout: Segundos de espera maxima
            
        Returns:
            bool: True si el modal se abrio, False si hubo timeout
        """
        wait = WebDriverWait(self._driver, timeout)
        try:
            # Esperar a que aparezca el contenedor de campos del modal
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".fieldContain"))
            )
            logger.debug("Modal de settings detectado")
            return True
        except TimeoutException:
            logger.warning("Timeout esperando el modal de settings")
            return False
    
    def get_username_from_modal(self) -> str:
        """
        Extrae el username del modal de settings abierto.
        
        Busca el campo con label "Username" y extrae el valor del label.labelbold
        que le sigue.
        
        Returns:
            str: Username del atleta o string vacio si no se encuentra
        """
        try:
            # Usar XPath para encontrar el label "Username" y su hermano labelbold
            username_label = self._driver.find_element(
                By.XPATH,
                "//div[@class='fieldContain']/label[@class='fieldTitle'][text()='Username']/following-sibling::label[@class='labelbold']"
            )
            username = username_label.text.strip()
            logger.debug(f"Username extraido del modal: {username}")
            return username
        except NoSuchElementException:
            logger.warning("No se encontro el campo Username en el modal")
            return ""
    
    def get_full_name_from_modal(self) -> str:
        """
        Extrae el nombre completo del modal de settings abierto.
        
        Busca el input con name="firstAndLastName" y extrae su valor.
        
        Returns:
            str: Nombre completo del atleta o string vacio si no se encuentra
        """
        try:
            name_input = self._driver.find_element(
                By.CSS_SELECTOR,
                'input[name="firstAndLastName"]'
            )
            full_name = name_input.get_attribute("value") or ""
            logger.debug(f"Nombre completo extraido del modal: {full_name}")
            return full_name.strip()
        except NoSuchElementException:
            logger.warning("No se encontro el campo First and Last Name en el modal")
            return ""
    
    
    def close_settings_modal(self) -> bool:
        """
        Cierra el modal de settings haciendo click en el icono de cerrar.
        Espera a que el overlay desaparezca para evitar clicks interceptados.
        
        Returns:
            bool: True si se cerro exitosamente, False en caso contrario
        """
        try:
            close_icon = self._driver.find_element(By.CSS_SELECTOR, "i.closeIcon")
            self._driver.execute_script("arguments[0].click();", close_icon)
            
            # Esperar a que el modal y overlay desaparezcan completamente
            try:
                self._wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.modalOverlayMask")))
                self._wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.tabbedSettingsModal")))
            except TimeoutException:
                logger.warning("Timeout esperando a que desaparezca el overlay del modal")
                
            time.sleep(0.5) # Pequeña espera adicional por seguridad
            logger.debug("Modal de settings cerrado")
            return True
        except NoSuchElementException:
            logger.warning("No se encontro el icono de cerrar modal")
            return False
        except Exception as e:
            logger.error(f"Error al cerrar modal de settings: {e}")
            return False
    
    # =========================================================================
    # METODOS PARA NAVEGACION POR GRUPOS
    # =========================================================================
    
    def _close_dropdown_menu(self, timeout: int = 10) -> None:
        """
        Cierra el menu dropdown de grupos y espera a que el backdrop desaparezca.
        
        MUI usa un backdrop invisible que bloquea clicks si no se cierra correctamente.
        Este metodo envia Escape y espera a que el backdrop desaparezca.
        
        Args:
            timeout: Segundos de espera maxima para que el backdrop desaparezca
        """
        try:
            # Enviar Escape para cerrar el menu
            self._driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            
            # Esperar a que el backdrop de MUI desaparezca
            wait = WebDriverWait(self._driver, timeout)
            wait.until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, '.MuiBackdrop-root'))
            )
            logger.debug("Dropdown cerrado y backdrop eliminado")
        except TimeoutException:
            logger.debug("Timeout esperando que desaparezca el backdrop (puede que ya no exista)")
        except Exception as e:
            logger.debug(f"Error al cerrar dropdown: {e}")
    
    def open_group_dropdown(self, timeout: int = 10) -> bool:
        """
        Abre el dropdown de grupos de atletas en la pagina #home.
        
        Espera a que el dropdown este disponible antes de hacer click,
        ya que el elemento puede tardar en cargarse. Verifica si ya esta
        abierto para evitar conflictos con el backdrop de MUI.
        
        Args:
            timeout: Segundos de espera maxima para que el dropdown este clickeable
        
        Returns:
            bool: True si se abrio exitosamente, False en caso contrario
        """
        wait = WebDriverWait(self._driver, timeout)
        try:
            # Esperar a que el dropdown este presente
            dropdown = wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    '.coachHomeHeaderSelect div[role="combobox"]'
                ))
            )
            
            # Verificar si ya esta abierto (aria-expanded="true")
            if dropdown.get_attribute("aria-expanded") == "true":
                logger.debug("Dropdown ya esta abierto")
                return True
            
            # Hacer scroll al elemento para asegurar visibilidad
            self._driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", 
                dropdown
            )
            time.sleep(0.3)
            
            # Click directo (no JS) para activar el dropdown de MUI
            dropdown.click()
            time.sleep(0.5)
            
            logger.debug("Dropdown de grupos abierto")
            return True
        except TimeoutException:
            logger.warning("Timeout esperando el dropdown de grupos")
            return False
        except Exception as e:
            logger.error(f"Error al abrir dropdown de grupos: {e}")
            return False
    
    def get_available_groups(self, timeout: int = 10) -> list:
        """
        Obtiene la lista de grupos disponibles en el dropdown.
        
        Primero abre el dropdown, luego extrae las opciones disponibles.
        Material UI renderiza el menu en un Popover separado del DOM.
        
        Args:
            timeout: Segundos de espera maxima
            
        Returns:
            list: Lista de dicts con nombre, valor y estado de seleccion de cada grupo
                  [{"name": "My Athletes", "value": "144561", "selected": True}, ...]
        """
        groups = []
        
        # Abrir dropdown
        if not self.open_group_dropdown(timeout):
            return groups
        
        wait = WebDriverWait(self._driver, timeout)
        
        try:
            # Material UI renderiza el menu en un Popover (MuiMenu-paper)
            # Esperar a que el menu popup sea visible
            logger.debug("Esperando menu popup...")
            wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.MuiMenu-paper'))
            )
            logger.debug("Menu popup visible")
            
            # Esperar a que aparezca la lista dentro del popup
            logger.debug("Esperando lista de opciones...")
            menu_list = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'ul[role="listbox"]'))
            )
            logger.debug("Lista de opciones visible")
            
            # Obtener todas las opciones (li con role="option")
            options = menu_list.find_elements(By.CSS_SELECTOR, 'li[role="option"]')
            logger.debug(f"Se encontraron {len(options)} opciones en el menu")
            
            for option in options:
                name = option.text.strip()
                value = option.get_attribute("data-value") or ""
                selected = "Mui-selected" in (option.get_attribute("class") or "")
                
                groups.append({
                    "name": name,
                    "value": value,
                    "selected": selected
                })
            
            logger.info(f"Se encontraron {len(groups)} grupos: {[g['name'] for g in groups]}")
            
            # Cerrar dropdown de forma robusta (espera que el backdrop desaparezca)
            self._close_dropdown_menu(timeout)
            
        except TimeoutException:
            logger.warning("Timeout esperando la lista de grupos")
            self._close_dropdown_menu(timeout)
        except Exception as e:
            logger.error(f"Error al obtener grupos: {e}")
            self._close_dropdown_menu(timeout)
        
        return groups
    
    def select_group(self, group_name: str, timeout: int = 10) -> bool:
        """
        Selecciona un grupo del dropdown por su nombre.
        
        Args:
            group_name: Nombre del grupo a seleccionar
            timeout: Segundos de espera maxima
            
        Returns:
            bool: True si se selecciono exitosamente, False en caso contrario
        """
        # Abrir dropdown
        if not self.open_group_dropdown(timeout):
            return False
        
        wait = WebDriverWait(self._driver, timeout)
        
        try:
            # Material UI renderiza el menu en un Popover
            wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.MuiMenu-paper'))
            )
            logger.debug("Menu popup visible para seleccion")
            
            # Esperar lista visible
            menu_list = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'ul[role="listbox"]'))
            )
            
            # Buscar la opcion por nombre
            options = menu_list.find_elements(By.CSS_SELECTOR, 'li[role="option"]')
            logger.debug(f"Opciones encontradas: {[opt.text.strip() for opt in options]}")
            
            for option in options:
                option_text = option.text.strip()
                if option_text == group_name:
                    # Hacer scroll al elemento y click directo
                    self._driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", 
                        option
                    )
                    time.sleep(0.2)
                    option.click()
                    time.sleep(0.5)
                    logger.info(f"Grupo '{group_name}' seleccionado")
                    return True
            
            logger.warning(f"No se encontro el grupo '{group_name}'")
            # Cerrar dropdown de forma robusta
            self._close_dropdown_menu(timeout)
            return False
            
        except TimeoutException:
            logger.warning("Timeout esperando la lista de grupos")
            self._close_dropdown_menu(timeout)
            return False
        except Exception as e:
            logger.error(f"Error al seleccionar grupo: {e}")
            self._close_dropdown_menu(timeout)
            return False
    
    # =========================================================================
    # UTILIDADES PARA COMPARACION DE NOMBRES
    # =========================================================================
    
    def _normalize_name(self, name: str) -> str:
        """
        Normaliza un nombre para comparacion: minusculas, sin acentos, sin espacios extra.
        
        Args:
            name: Nombre a normalizar
            
        Returns:
            str: Nombre normalizado
        """
        import unicodedata
        
        if not name:
            return ""
        
        # Convertir a minusculas
        normalized = name.lower().strip()
        
        # Remover acentos
        normalized = unicodedata.normalize('NFD', normalized)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        
        # Normalizar espacios multiples a uno solo
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    # Longitud minima para considerar un prefijo como match valido.
    # Evita falsos positivos con prefijos muy cortos (ej. "Al" matcheando "Alberto").
    _MIN_PREFIX_LENGTH = 3
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """
        Compara si el primer nombre de ambos strings coincide o es abreviacion.
        
        Compara el primer nombre (primera palabra) de cada string.
        Soporta nombres abreviados usando startswith bidireccional:
        si un nombre es prefijo del otro (con minimo _MIN_PREFIX_LENGTH caracteres),
        se considera match. Ej: "Lore" matchea "Lorena", "Ale" matchea "Alejandro".
        
        Args:
            name1: Primer nombre completo
            name2: Segundo nombre completo
            
        Returns:
            bool: True si el primer nombre coincide o es prefijo valido
        """
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        
        if not n1 or not n2:
            return False
        
        # Extraer primer nombre de cada uno
        words1 = n1.split()
        words2 = n2.split()
        
        first1 = words1[0] if words1 else ""
        first2 = words2[0] if words2 else ""
        
        if not first1 or not first2:
            return False
        
        # Igualdad exacta
        if first1 == first2:
            return True
        
        # Prefijo bidireccional: "lore" -> "lorena" o "lorena" -> "lore"
        # Ambos deben tener al menos _MIN_PREFIX_LENGTH caracteres
        prefix_len = min(len(first1), len(first2))
        if prefix_len >= self._MIN_PREFIX_LENGTH:
            if first1.startswith(first2) or first2.startswith(first1):
                return True
        
        return False
    
    def _filter_tiles_by_name(
        self, 
        tiles: list, 
        expected_name: str, 
        timeout: int = 5
    ) -> list:
        """
        Filtra tiles de atletas que coincidan con el nombre esperado.
        
        Args:
            tiles: Lista de WebElements de tiles de atletas
            expected_name: Nombre esperado del atleta
            timeout: Timeout para operaciones
            
        Returns:
            list: Lista de tuplas (tile, tile_name) que coinciden con el nombre
        """
        candidates = []
        
        for tile in tiles:
            tile_name = self.get_athlete_name_from_tile(tile)
            if self._names_match(tile_name, expected_name):
                candidates.append((tile, tile_name))
                logger.debug(f"Candidato encontrado: '{tile_name}' coincide con '{expected_name}'")
        
        return candidates
    
    # =========================================================================
    # METODOS DE BUSQUEDA POR USERNAME
    # =========================================================================
    
    def _search_by_name_in_group(
        self,
        username: str,
        group_name: str,
        expected_name: str,
        timeout: int = 10
    ) -> dict:
        """
        Busca un username filtrando tiles por primer nombre (busqueda rapida).
        
        Filtra tiles cuyo nombre visible coincide con el primer nombre de
        expected_name (ej. "Emiliano" de "Emiliano Perez Sanchez"), y solo
        abre modales de esos candidatos para verificar el username.
        
        Args:
            username: Username a buscar (case-insensitive)
            group_name: Nombre del grupo actual (para logging y resultado)
            expected_name: Nombre completo esperado (se usa el primer nombre)
            timeout: Segundos de espera por operacion
            
        Returns:
            dict: Resultado parcial con found/full_name/tiles_checked
        """
        result = {
            "found": False,
            "username": username,
            "full_name": "",
            "group": group_name,
            "tiles_checked": 0
        }
        
        tiles = self.get_athlete_tiles(timeout)
        
        if not tiles:
            logger.info(f"No hay atletas en el grupo {group_name}")
            return result
        
        candidates = self._filter_tiles_by_name(tiles, expected_name, timeout)
        
        if not candidates:
            logger.info(
                f"No hay atletas con primer nombre similar a '{expected_name}' "
                f"en grupo '{group_name}'"
            )
            return result
        
        logger.info(
            f"Busqueda por nombre: {len(candidates)} candidatos de {len(tiles)} atletas "
            f"coinciden con '{expected_name}' en grupo '{group_name}'"
        )
        
        for tile, tile_name in candidates:
            logger.debug(f"Verificando candidato: {tile_name}")
            
            if not self.click_athlete_settings_button(tile, timeout):
                logger.warning(f"No se pudo abrir settings para {tile_name}")
                continue
            
            if not self.wait_for_settings_modal(timeout):
                logger.warning(f"Modal no se abrio para {tile_name}")
                continue
            
            result["tiles_checked"] += 1
            modal_username = self.get_username_from_modal()
            
            if modal_username.lower() == username.lower():
                full_name = self.get_full_name_from_modal()
                result["found"] = True
                result["full_name"] = full_name
                
                print(f"El nombre del usuario {username} es {full_name}")
                logger.info(
                    f"Match encontrado (por nombre): usuario '{username}' = "
                    f"'{full_name}' en grupo '{group_name}'"
                )
                
                self.close_settings_modal()
                return result
            
            self.close_settings_modal()
            time.sleep(0.2)
        
        logger.info(
            f"Candidatos por nombre verificados sin match de username en '{group_name}'. "
            f"Verificados: {result['tiles_checked']}"
        )
        return result
    
    def _search_by_username_in_group(
        self,
        username: str,
        group_name: str,
        result: dict,
        timeout: int = 10
    ) -> dict:
        """
        Itera todos los tiles del grupo abriendo cada modal para verificar username.
        
        Es el metodo de fuerza bruta: abre el modal de CADA atleta para comparar
        el username. Re-obtiene los tiles del DOM para evitar stale elements.
        
        Args:
            username: Username a buscar (case-insensitive)
            group_name: Nombre del grupo (para logging)
            result: Diccionario de resultado parcial (acumula tiles_checked)
            timeout: Segundos de espera por operacion
            
        Returns:
            dict: Resultado actualizado con found/full_name si hay match
        """
        tiles = self.get_athlete_tiles(timeout)
        
        if not tiles:
            logger.info(f"No hay atletas en el grupo {group_name} (iteracion completa)")
            return result
        
        logger.info(f"Iteracion completa: verificando {len(tiles)} atletas en '{group_name}'...")
        
        for i, tile in enumerate(tiles):
            tile_name = self.get_athlete_name_from_tile(tile)
            logger.debug(f"Verificando atleta {i+1}/{len(tiles)}: {tile_name}")
            
            if not self.click_athlete_settings_button(tile, timeout):
                logger.warning(f"No se pudo abrir settings para {tile_name}")
                continue
            
            if not self.wait_for_settings_modal(timeout):
                logger.warning(f"Modal no se abrio para {tile_name}")
                continue
            
            result["tiles_checked"] += 1
            modal_username = self.get_username_from_modal()
            
            if modal_username.lower() == username.lower():
                full_name = self.get_full_name_from_modal()
                result["found"] = True
                result["full_name"] = full_name
                
                print(f"El nombre del usuario {username} es {full_name}")
                logger.info(
                    f"Match encontrado (iteracion completa): usuario '{username}' = "
                    f"'{full_name}' en grupo '{group_name}'"
                )
                
                self.close_settings_modal()
                return result
            
            self.close_settings_modal()
            time.sleep(0.2)
        
        logger.info(f"No se encontro match en grupo {group_name} (iteracion completa)")
        return result
    
    def _navigate_to_group(self, group_name: str, current_group: str, timeout: int = 10) -> bool:
        """
        Navega al grupo indicado si no es el grupo actual.
        
        Args:
            group_name: Grupo destino
            current_group: Grupo donde estamos actualmente
            timeout: Segundos de espera
            
        Returns:
            bool: True si se pudo navegar (o ya estamos ahi)
        """
        if group_name == current_group:
            return True
        
        logger.info(f"Cambiando a grupo: {group_name}")
        if not self.select_group(group_name, timeout):
            logger.warning(f"No se pudo seleccionar el grupo {group_name}")
            return False
        
        time.sleep(1)
        return True
    
    def _get_remaining_group_names(self, visited: set, timeout: int = 10) -> list:
        """
        Obtiene nombres de grupos aun no visitados via el dropdown.
        
        Se llama de forma lazy (despues de haber interactuado con la pagina)
        para que el DOM y los componentes de Material UI esten listos.
        
        Args:
            visited: Set de nombres de grupo ya visitados
            timeout: Segundos de espera
            
        Returns:
            list: Nombres de grupos pendientes de visitar
        """
        groups = self.get_available_groups(timeout)
        remaining = [g["name"] for g in groups if g["name"] not in visited]
        logger.info(f"Grupos restantes por visitar: {remaining}")
        return remaining
    
    def find_athlete_by_username(
        self, 
        username: str, 
        expected_name: str = None,
        timeout: int = 10
    ) -> dict:
        """
        Busca un atleta por su username iterando por todos los grupos.
        
        Estrategia de busqueda en dos pases:
        
        PASE 1 (rapido, por nombre): Si se proporciona expected_name, recorre
        todos los grupos filtrando tiles por primer nombre visible. Solo abre
        modales de candidatos cuyo primer nombre coincide. Si lo encuentra,
        retorna inmediatamente.
        
        PASE 2 (fallback, por username): Si el pase 1 no encuentra match en
        ningun grupo, recorre todos los grupos de nuevo iterando CADA tile y
        abriendo su modal para verificar el username directamente. Esto cubre
        casos donde el nombre en AirTable no coincide con el de TrainingPeaks.
        
        Si no se proporciona expected_name, solo ejecuta el pase 2.
        
        La lista de grupos se obtiene de forma lazy (despues de buscar en el
        primer grupo) para que el dropdown de Material UI este listo.
        
        Args:
            username: Username a buscar (case-insensitive)
            expected_name: Nombre esperado del atleta (opcional, acelera la busqueda)
            timeout: Segundos de espera por operacion
            
        Returns:
            dict: Resultado de la busqueda
                  {"found": True/False, "username": str, "full_name": str, "group": str}
        """
        total_tiles_checked = 0
        current_group = "My Athletes"
        remaining_groups = []  # Se obtiene lazy despues del primer grupo
        
        # =====================================================================
        # PASE 1: Busqueda rapida por primer nombre (si hay expected_name)
        # =====================================================================
        if expected_name:
            logger.info(
                f"PASE 1 - Busqueda por nombre: username='{username}', "
                f"expected_name='{expected_name}'"
            )
            
            # 1a. Buscar en el grupo actual (My Athletes) primero
            result = self._search_by_name_in_group(
                username=username,
                group_name=current_group,
                expected_name=expected_name,
                timeout=timeout
            )
            total_tiles_checked += result["tiles_checked"]
            
            if result["found"]:
                result["tiles_checked"] = total_tiles_checked
                return result
            
            # 1b. Obtener grupos restantes (lazy: la pagina ya esta interactiva)
            remaining_groups = self._get_remaining_group_names(
                visited={current_group}, timeout=timeout
            )
            
            # 1c. Buscar por nombre en los demas grupos
            for group_name in remaining_groups:
                if not self._navigate_to_group(group_name, current_group, timeout):
                    continue
                current_group = group_name
                
                result = self._search_by_name_in_group(
                    username=username,
                    group_name=group_name,
                    expected_name=expected_name,
                    timeout=timeout
                )
                total_tiles_checked += result["tiles_checked"]
                
                if result["found"]:
                    result["tiles_checked"] = total_tiles_checked
                    return result
            
            logger.info(
                f"PASE 1 finalizado: no se encontro '{username}' por nombre en ningun grupo. "
                f"Tiles verificados: {total_tiles_checked}. Iniciando PASE 2 (fallback)..."
            )
        
        # =====================================================================
        # PASE 2: Fallback - iterar todos los tiles en todos los grupos
        # =====================================================================
        logger.info(f"PASE 2 - Iteracion completa: buscando username='{username}' en todos los grupos")
        
        result = {
            "found": False,
            "username": username,
            "full_name": "",
            "group": "",
            "tiles_checked": total_tiles_checked
        }
        
        # Si no se obtuvieron grupos aun (expected_name era None), obtenerlos
        # despues de buscar en el primer grupo del pase 2
        groups_fetched = len(remaining_groups) > 0
        
        # 2a. Buscar en "My Athletes" primero
        if not self._navigate_to_group("My Athletes", current_group, timeout):
            logger.warning("No se pudo navegar a My Athletes para PASE 2")
        else:
            current_group = "My Athletes"
            result = self._search_by_username_in_group(
                username=username,
                group_name=current_group,
                result=result,
                timeout=timeout
            )
            if result["found"]:
                return result
        
        # 2b. Obtener grupos si aun no se han obtenido
        if not groups_fetched:
            remaining_groups = self._get_remaining_group_names(
                visited={current_group}, timeout=timeout
            )
        
        # 2c. Iterar grupos restantes
        for group_name in remaining_groups:
            if not self._navigate_to_group(group_name, current_group, timeout):
                continue
            current_group = group_name
            
            result = self._search_by_username_in_group(
                username=username,
                group_name=group_name,
                result=result,
                timeout=timeout
            )
            
            if result["found"]:
                return result
        
        logger.warning(f"Usuario '{username}' no encontrado en ningun grupo (ambos pases agotados)")
        return result

    def discover_username(self, athlete_name: str, full_name: Optional[str] = None, timeout: int = 10) -> Optional[str]:
        """
        Busca al atleta por su nombre en TrainingPeaks y extrae su username.
        Itera por los grupos si es necesario.
        
        Args:
            athlete_name: Nombre corto del atleta
            full_name: Nombre completo (opcional)
            timeout: Timeout por operacion
            
        Returns:
            Optional[str]: Username encontrado o None
        """
        logger.info(f"Iniciando descubrimiento de username para: {athlete_name}")
        
        # 1. Obtener grupos
        groups = self.get_available_groups(timeout)
        if not groups:
            # Si no hay grupos, intentar al menos en la vista actual
            logger.info("No se detectaron grupos, buscando en vista actual...")
            return self._discover_in_current_view(athlete_name, full_name, timeout)
            
        # 2. Iterar por cada grupo
        for group in groups:
            group_name = group["name"]
            logger.info(f"Buscando en grupo: {group_name}")
            
            if self.select_group(group_name, timeout):
                username = self._discover_in_current_view(athlete_name, full_name, timeout)
                if username:
                    logger.info(f"Username '{username}' descubierto en grupo '{group_name}'")
                    return username
                    
        logger.warning(f"No se pudo descubrir username para {athlete_name} tras revisar todos los grupos")
        return None

    def _discover_in_current_view(self, athlete_name: str, full_name: Optional[str] = None, timeout: int = 10) -> Optional[str]:
        """Auxiliar para buscar username en la vista (#home) actual."""
        tiles = self.get_athlete_tiles(timeout)
        if not tiles:
            return None
            
        # Nombres objetivo normalizados
        targets = {self._normalize_name(athlete_name)}
        if full_name:
            targets.add(self._normalize_name(full_name))
            
        for tile in tiles:
            tile_name = self.get_athlete_name_from_tile(tile)
            if not tile_name:
                continue
                
            norm_name = self._normalize_name(tile_name)
            
            # Coincidencia exacta o parcial
            is_match = norm_name in targets or any(t in norm_name or norm_name in t for t in targets if len(t) > 3)
            
            if is_match:
                logger.info(f"Coincidencia encontrada: {tile_name}. Abriendo settings...")
                if self.click_athlete_settings_button(tile, timeout):
                    if self.wait_for_settings_modal(timeout):
                        username = self.get_username_from_modal()
                        self.close_settings_modal()
                        if username:
                            return username
        return None
