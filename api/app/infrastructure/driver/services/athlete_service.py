"""
Servicio de gestion de atletas para TrainingPeaks.
Maneja la seleccion y navegacion en la biblioteca de atletas.
"""
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    
    def click_athlete_settings_button(self, athlete_tile, timeout: int = 5) -> bool:
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
        time.sleep(0.3)
        
        settings_btn = None
        
        # Estrategia 1: Buscar el button dentro del div con aria-label (estructura de #home)
        try:
            settings_btn = athlete_tile.find_element(
                By.CSS_SELECTOR, 
                'div[aria-label="Go to this athlete\'s settings"] button'
            )
            if settings_btn and settings_btn.is_displayed():
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
                if settings_btn and settings_btn.is_displayed():
                    logger.debug("Boton de settings encontrado via SettingsIcon")
            except NoSuchElementException:
                pass
        
        if not settings_btn:
            logger.warning("No se encontro el boton de settings en el tile")
            return False
        
        try:
            # Usar JavaScript click para evitar problemas de overlay
            self._driver.execute_script("arguments[0].click();", settings_btn)
            logger.info("Click en boton de settings realizado")
            
            # Esperar brevemente para que el modal se abra
            time.sleep(0.5)
            return True
            
        except Exception as e:
            logger.error(f"Error al hacer click en settings: {e}")
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
        
        Returns:
            bool: True si se cerro exitosamente, False en caso contrario
        """
        try:
            close_icon = self._driver.find_element(By.CSS_SELECTOR, "i.closeIcon")
            self._driver.execute_script("arguments[0].click();", close_icon)
            time.sleep(0.3)
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
    
    def _close_dropdown_menu(self, timeout: int = 5) -> None:
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
    # METODO PRINCIPAL DE BUSQUEDA POR USERNAME
    # =========================================================================
    
    def _search_in_current_group(self, username: str, group_name: str, timeout: int = 10) -> dict:
        """
        Busca un username en los atletas del grupo actualmente seleccionado.
        
        Este metodo no cambia de grupo, solo itera los atletas visibles.
        
        Args:
            username: Username a buscar (case-insensitive)
            group_name: Nombre del grupo actual (para logging y resultado)
            timeout: Segundos de espera por operacion
            
        Returns:
            dict: Resultado parcial de la busqueda con tiles_checked actualizado
        """
        result = {
            "found": False,
            "username": username,
            "full_name": "",
            "group": group_name,
            "tiles_checked": 0
        }
        
        # Obtener tiles de atletas en el grupo actual
        tiles = self.get_athlete_tiles(timeout)
        
        if not tiles:
            logger.info(f"No hay atletas en el grupo {group_name}")
            return result
        
        logger.info(f"Buscando en grupo '{group_name}' con {len(tiles)} atletas")
        
        # Iterar por cada atleta en el grupo
        for i, tile in enumerate(tiles):
            tile_name = self.get_athlete_name_from_tile(tile)
            logger.debug(f"Verificando atleta {i+1}/{len(tiles)}: {tile_name}")
            
            # Click en settings
            if not self.click_athlete_settings_button(tile, timeout):
                logger.warning(f"No se pudo abrir settings para {tile_name}")
                continue
            
            # Esperar modal
            if not self.wait_for_settings_modal(timeout):
                logger.warning(f"Modal no se abrio para {tile_name}")
                continue
            
            result["tiles_checked"] += 1
            
            # Extraer username del modal
            modal_username = self.get_username_from_modal()
            
            # Comparar usernames (case-insensitive)
            if modal_username.lower() == username.lower():
                # Match encontrado
                full_name = self.get_full_name_from_modal()
                
                result["found"] = True
                result["full_name"] = full_name
                
                # Imprimir en consola
                print(f"El nombre del usuario {username} es {full_name}")
                logger.info(f"Match encontrado: usuario '{username}' = '{full_name}' en grupo '{group_name}'")
                
                # Cerrar modal y retornar
                self.close_settings_modal()
                return result
            
            # No hay match, cerrar modal y continuar
            self.close_settings_modal()
            time.sleep(0.2)
        
        logger.info(f"No se encontro match en grupo {group_name}")
        return result
    
    def find_athlete_by_username(self, username: str, timeout: int = 10) -> dict:
        """
        Busca un atleta por su username iterando por todos los grupos y atletas.
        
        El flujo optimizado es:
        1. Busca primero en el grupo actual (My Athletes) sin abrir dropdown
        2. Si no hay match, abre dropdown y obtiene lista de grupos
        3. Itera por los grupos restantes buscando el username
        4. Si hay match: extrae nombre completo, imprime en consola, retorna
        
        Args:
            username: Username a buscar (case-insensitive)
            timeout: Segundos de espera por operacion
            
        Returns:
            dict: Resultado de la busqueda
                  {"found": True/False, "username": str, "full_name": str, "group": str}
        """
        total_tiles_checked = 0
        
        # 1. Buscar primero en el grupo actual (My Athletes por default)
        current_group = "My Athletes"
        logger.info(f"Buscando en grupo actual: {current_group}")
        
        result = self._search_in_current_group(username, current_group, timeout)
        total_tiles_checked += result["tiles_checked"]
        
        if result["found"]:
            return result
        
        # 2. No se encontro en grupo actual, abrir dropdown para obtener otros grupos
        logger.info("No se encontro en grupo actual, buscando en otros grupos...")
        
        groups = self.get_available_groups(timeout)
        
        if not groups:
            logger.warning("No se encontraron grupos de atletas")
            result["tiles_checked"] = total_tiles_checked
            return result
        
        # 3. Iterar por grupos restantes (excluyendo el ya visitado)
        visited_groups = {current_group}
        
        for group in groups:
            group_name = group["name"]
            
            # Saltar grupos ya visitados
            if group_name in visited_groups:
                continue
            
            logger.info(f"Cambiando a grupo: {group_name}")
            
            # Seleccionar el grupo
            if not self.select_group(group_name, timeout):
                logger.warning(f"No se pudo seleccionar el grupo {group_name}")
                continue
            
            # Esperar a que carguen los atletas
            time.sleep(1)
            
            # Buscar en este grupo
            result = self._search_in_current_group(username, group_name, timeout)
            total_tiles_checked += result["tiles_checked"]
            
            if result["found"]:
                result["tiles_checked"] = total_tiles_checked
                return result
            
            visited_groups.add(group_name)
        
        # No se encontro en ningun grupo
        logger.warning(f"Usuario '{username}' no encontrado en ningun grupo")
        return {
            "found": False,
            "username": username,
            "full_name": "",
            "group": "",
            "tiles_checked": total_tiles_checked
        }

