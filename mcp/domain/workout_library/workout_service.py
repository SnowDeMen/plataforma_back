"""
Workout Service - Servicios de gestión de workouts individuales
"""

from typing import Optional, Dict, Any, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains
from ..core import get_driver, get_wait
from .library_service import is_workout_library_open, workout_library


def click_workout(title, folder=None, exact=False, timeout=12):
    """
    Click al workout cuyo <p class='title'> coincide con `title`.
    - folder: (opcional) nombre del folder donde buscar.
    - exact:  True -> match exacto | False -> 'contains' del texto.
    """
    driver = get_driver()
    wait = get_wait()
    
    # 1) si viene folder, primero anclamos al contenedor de ese folder
    if folder:
        header_xpath = (
            "//div[contains(@class,'titleContain') and "
            "(normalize-space()='{t}' or @data-tooltip='{t}')]"
            "/ancestor::div[contains(@class,'listHeader')]"
        ).format(t=folder)
        # sube al contenedor del folder
        container_xpath = header_xpath + "/ancestor::div[contains(@class,'workoutLibraryFolder')]"
    else:
        container_xpath = ""  # búsqueda global

    # 2) ancla por el <p class='title'> con el texto del workout
    pred = f"normalize-space()='{title}'" if exact else f"contains(normalize-space(), '{title}')"
    xp_title = f"{container_xpath}//p[contains(@class,'title') and {pred}]"

    title_el = wait.until(EC.presence_of_element_located((By.XPATH, xp_title)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", title_el)

    # 3) intenta clicks escalonados: título -> tile -> item
    candidates = [title_el]
    for rel in [
        "ancestor::div[contains(@class,'workoutLibraryWorkoutTile')]",
        "ancestor::div[contains(@class,'workoutLibraryItem')]",
    ]:
        try:
            el = title_el.find_element(By.XPATH, rel)
            candidates.append(el)
        except NoSuchElementException:
            pass

    last_err = None
    for el in candidates:
        try:
            wait.until(lambda d: el.is_displayed() and el.is_enabled())
            el.click()
            return
        except Exception as e1:
            last_err = e1
            try:
                ActionChains(driver).move_to_element(el).pause(0.05).click().perform()
                return
            except Exception as e2:
                last_err = e2
                try:
                    driver.execute_script("arguments[0].click();", el)
                    return
                except Exception as e3:
                    last_err = e3
                    continue

    raise TimeoutException(f"No pude clickear el workout '{title}'. Último error: {last_err}")


def click_selected_workout_tomahawk_button(timeout=20):
    """
    Hace clic en el botón del menú (tomahawk) del modal que aparece
    al seleccionar un workout dentro de la Workout Library.

    Retorna:
      True  -> si se pudo hacer clic
      False -> si no se encontró o no fue clickeable a tiempo
    """
    driver = get_driver()
    wait = get_wait()
    
    try:
        # 1) Espera a que el popover modal exista (solo aparece cuando el item está seleccionado)
        #    Usamos una cadena de clases estable dentro del popover
        popover = wait.until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "div.MuiPopover-root.workoutLibraryItemTomahawk.MuiModal-root"
            ))
        )

        # 2) Dentro del modal, encontrar el botón del menú (tomahawk)
        #    Estructura objetivo (más robusta que el full CSS absoluto):
        #    .MuiPaper-root.MuiPopover-paper
        #       .workoutLibraryItemTomahawkHeader
        #           .workoutLibraryItemTomahawkMenu > button
        button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "div.MuiPopover-root.workoutLibraryItemTomahawk.MuiModal-root "
                "div.MuiPaper-root.MuiPopover-paper "
                "div.workoutLibraryItemTomahawkHeader "
                "div.workoutLibraryItemTomahawkMenu > button"
            ))
        )

        # 3) Scroll al centro y click (con fallback JS por si hay overlay)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", button)
        try:
            button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", button)

        print("Tomahawk del workout (modal) clickeado correctamente ✅")
        return True

    except Exception as e:
        print(f"No se pudo hacer clic en el tomahawk del workout: {e}")
        return False


def click_edit_workout_button():
    """
    Hace clic en la primera opción (li:nth-child(1)) del menú desplegable
    del tomahawk de un workout seleccionado dentro de la Workout Library.

    Retorna:
      True  -> si se hizo clic correctamente
      False -> si no se encontró o no fue clickeable
    """
    driver = get_driver()
    wait = get_wait()
    
    try:
        # Espera a que aparezca el menú desplegable del tomahawk (popover de opciones)
        menu_item = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "#wrapper > div > div > div.appContainerLibrayAndContentContainer > "
            "div.libraries.open > div.activeLibraryContainer > div > "
            "div.workoutLibraryFoldersContainer.libraryContents > "
            "div.workoutLibraryMainComponent.workoutLibraryFolder.expanded > "
            "div.itemsContainer > div.workoutLibraryItem.selected > "
            "div.MuiPopover-root.workoutLibraryItemTomahawk.MuiModal-root.css-782n7b-MuiModal-root-MuiPopover-root > "
            "div.MuiPaper-root.MuiPaper-elevation.MuiPaper-rounded.MuiPaper-elevation8.MuiPopover-paper.css-v2zkln-MuiPaper-root-MuiPopover-paper > "
            "div.workoutLibraryItemTomahawkHeader > div.workoutLibraryItemTomahawkMenu > div > "
            "div.MuiPaper-root.MuiPaper-elevation.MuiPaper-rounded.MuiPaper-elevation8.MuiPopover-paper.MuiMenu-paper.MuiMenu-paper.css-cw3q0e-MuiPaper-root-MuiPopover-paper-MuiMenu-paper > ul > li:nth-child(1)"
        )))
        
        # Asegura visibilidad y clic
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", menu_item)
        try:
            menu_item.click()
        except Exception:
            driver.execute_script("arguments[0].click();", menu_item)

        print("Primera opción del menú tomahawk clickeada correctamente ✅")
        return True

    except Exception as e:
        print(f"No se pudo hacer clic en la primera opción del menú tomahawk: {e}")
        return False


def click_delete_workout_button(timeout=20):
    """
    Hace clic en la opción roja (li.redColor) del menú del tomahawk
    dentro del modal del workout seleccionado en la Workout Library.

    Retorna:
      True  -> si se hizo clic correctamente
      False -> si no se encontró o no fue clickeable
    """
    driver = get_driver()
    wait = get_wait()
    
    try:
        # 1) Asegura que el popover del tomahawk esté presente (solo existe cuando el modal está abierto)
        popover = wait.until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "div.MuiPopover-root.workoutLibraryItemTomahawk.MuiModal-root"
            ))
        )

        # 2) Dentro del popover, espera el menú (otra hoja/paper) y localiza la opción roja
        red_option = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                # más robusto que el path completo: cualquier item de menú con la clase 'redColor'
                "div.MuiPopover-root.workoutLibraryItemTomahawk.MuiModal-root "
                "div.MuiPaper-root.MuiPopover-paper.MuiMenu-paper "
                "ul > li.MuiMenuItem-root.redColor"
            ))
        )

        # 3) Scroll al centro y click (con fallback JS si hay overlay)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", red_option)
        try:
            red_option.click()
        except Exception:
            driver.execute_script("arguments[0].click();", red_option)

        print("Opción roja del menú tomahawk clickeada correctamente ✅")
        return True

    except Exception as e:
        print(f"No se pudo hacer clic en la opción roja del menú tomahawk: {e}")
        return False


def click_delete_workout_confirm_button(timeout=15):
    """
    Hace clic en el botón principal (rojo) dentro del promptModal (confirmación de acción).
    Retorna True si se hizo clic correctamente, False si no se encontró o no fue clickeable.
    """
    driver = get_driver()
    wait = get_wait()
    
    try:
        # Espera que el modal aparezca
        modal = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "body > div.promptModal.MuiModal-root"
        )))

        # Espera que el botón rojo de confirmación sea clickeable
        confirm_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "body > div.promptModal.MuiModal-root "
                "div.promptModalContainer button.MuiButton-containedError.promptModalPrimaryButton"
            ))
        )

        # Scroll al centro y clic
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", confirm_button)
        try:
            confirm_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", confirm_button)

        print("Botón rojo de confirmación (promptModal) clickeado correctamente ✅")
        return True

    except Exception as e:
        print(f"No se pudo hacer clic en el botón del promptModal: {e}")
        return False


def get_workout_modal_data(timeout=20):
    """
    Extrae los datos del modal de Workout seleccionado:
      - Planned / Completed (Duration, Distance, Avg Speed, Calories, Elevation Gain, TSS, IF, Normalized Power, Work)
      - Min / Avg / Max (Heart Rate, Power, Elevation, Cadence, Speed, Pace, Temperature)
      - Descripción
      - Adjuntos
      - Estructura del workout (texto)
    Retorna un dict con la información o None si no se encuentra el modal/summary.
    """
    driver = get_driver()
    
    def _safe(el_fn, default=None):
        try:
            return el_fn()
        except Exception:
            return default

    def _get_by_id_value(elem_id):
        el = _safe(lambda: driver.find_element(By.ID, elem_id))
        if not el:
            return None
        # Inputs tienen el valor en el atributo 'value'
        return _safe(lambda: el.get_attribute("value"), None)

    def _get_css_text(css):
        el = _safe(lambda: driver.find_element(By.CSS_SELECTOR, css))
        if not el:
            return None
        return _safe(lambda: el.text.strip(), None)

    # 1) Asegura que el bloque principal esté presente
    try:
        summary_root = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.summary"))
        )
        # Mejorar estabilidad de scrolling
        driver.execute_script("arguments[0].scrollIntoView({block:'start'});", summary_root)
    except Exception:
        print("No se encontró el contenedor principal del modal (.summary).")
        return None

    # 2) Planned / Completed: IDs conocidos del snippet
    planned_completed = {
        "duration": {
            "planned": _get_by_id_value("totalTimePlannedField"),
            "completed": _get_by_id_value("totalTimeCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .durationStatsRow .workoutStatsUnitLabel label")
        },
        "distance": {
            "planned": _get_by_id_value("distancePlannedField"),
            "completed": _get_by_id_value("distanceCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .distanceStatsRow .workoutStatsUnitLabel label")
        },
        "averageSpeed": {
            "planned": _get_by_id_value("averageSpeedPlannedField"),
            "completed": _get_by_id_value("averageSpeedCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .averageSpeedStatsRow .workoutStatsUnitLabel label")
        },
        "calories": {
            "planned": _get_by_id_value("caloriesPlannedField"),
            "completed": _get_by_id_value("caloriesCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .caloriesStatsRow .workoutStatsUnitLabel label")
        },
        "elevationGain": {
            "planned": _get_by_id_value("elevationGainPlannedField"),
            "completed": _get_by_id_value("elevationGainCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .elevationGainStatsRow .workoutStatsUnitLabel label")
        },
        "tss": {
            "planned": _get_by_id_value("tssPlannedField"),
            "completed": _get_by_id_value("tssCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .TSSStatsRow .workoutStatsUnitLabel label")
        },
        "if": {
            "planned": _get_by_id_value("ifPlannedField"),
            "completed": _get_by_id_value("ifCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .IFStatsRow .workoutStatsUnitLabel label")
        },
        "normalizedPower": {
            "planned": _get_by_id_value("normalizedPowerPlanned"),   # disabled
            "completed": _get_by_id_value("normalizedPowerCompleted"),
            "units": _get_css_text("#workoutPlannedCompletedStats .normalizedPowerStatsRow .workoutStatsUnitLabel label")
        },
        "work_kJ": {
            "planned": _get_by_id_value("energyPlannedField"),
            "completed": _get_by_id_value("energyCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .energyStatsRow .workoutStatsUnitLabel label")
        },
        # Campos ocultos/condicionales (pueden venir como None)
        "normalizedPace": {
            "planned": _get_by_id_value("normalizedPacePlannedField"),
            "completed": _get_by_id_value("normalizedPaceCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .normalizedPaceStatsRow .workoutStatsUnitLabel label")
        },
        "averagePace": {
            "planned": _get_by_id_value("averagePacePlannedField"),
            "completed": _get_by_id_value("averagePaceCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .averagePaceStatsRow .workoutStatsUnitLabel label")
        },
        "fatCalories": {
            "planned": _get_by_id_value("fatCaloriesPlannedField"),
            "completed": _get_by_id_value("fatCaloriesCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .fatCaloriesStatsRow .workoutStatsUnitLabel label")
        },
        "carbCalories": {
            "planned": _get_by_id_value("carbCaloriesPlannedField"),
            "completed": _get_by_id_value("carbCaloriesCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .carbCaloriesStatsRow .workoutStatsUnitLabel label")
        },
        "elevationLoss": {
            "planned": _get_by_id_value("elevationLossPlannedField"),
            "completed": _get_by_id_value("elevationLossCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .elevationLossStatsRow .workoutStatsUnitLabel label")
        },
    }

    # 3) Min / Avg / Max
    min_avg_max = {
        "heartRate": {
            "min": _get_by_id_value("hrMinField"),
            "avg": _get_by_id_value("hrAvgField"),
            "max": _get_by_id_value("hrMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .heartRateSummaryRow .workoutStatsUnitLabel label")
        },
        "power": {
            "min": _get_by_id_value("powerMinField"),
            "avg": _get_by_id_value("powerAvgField"),
            "max": _get_by_id_value("powerMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .powerSummaryRow .workoutStatsUnitLabel label")
        },
        "elevation": {
            "min": _get_by_id_value("elevationMinField"),
            "avg": _get_by_id_value("elevationAvgField"),
            "max": _get_by_id_value("elevationMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .elevationSummaryRow .workoutStatsUnitLabel label")
        },
        "cadence": {
            "min": _get_by_id_value("cadenceMinField"),
            "avg": _get_by_id_value("cadenceAvgField"),
            "max": _get_by_id_value("cadenceMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .cadenceSummaryRow .workoutStatsUnitLabel label")
        },
        "speed": {
            "min": _get_by_id_value("speedMinField"),
            "avg": _get_by_id_value("speedAvgField"),
            "max": _get_by_id_value("speedMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .speedSummaryRow .workoutStatsUnitLabel label")
        },
        "pace": {
            "min": _get_by_id_value("paceMinField"),
            "avg": _get_by_id_value("paceAvgField"),
            "max": _get_by_id_value("paceMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .paceSummaryRow .workoutStatsUnitLabel label")
        },
        "temperature": {
            "min": _get_by_id_value("tempMinField"),
            "avg": _get_by_id_value("tempAvgField"),
            "max": _get_by_id_value("tempMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .temperatureSummaryRow .workoutStatsUnitLabel label")
        },
    }

    # 4) Descripción (usa printable si existe, si no el contenteditable)
    description = _get_css_text("#descriptionPrintable")
    if not description:
        description_el = _safe(lambda: driver.find_element(By.CSS_SELECTOR, "#descriptionInput"))
        if description_el:
            description = _safe(lambda: description_el.get_attribute("innerText") or description_el.text, "")

    # 5) Adjuntos
    attachments = []
    try:
        links = driver.find_elements(By.CSS_SELECTOR, ".attachmentsContainer ul.files li a")
        for a in links:
            attachments.append({
                "name": _safe(lambda: a.text.strip(), None),
                "href": _safe(lambda: a.get_attribute("href"), None),
                "title": _safe(lambda: a.get_attribute("title"), None),
            })
    except Exception:
        pass

    # 6) Estructura del workout (texto)
    workout_details = {
        "header": _get_css_text(".workoutStructureTextHeader"),
        "steps": []
    }
    try:
        # Toma cada <li> y recoge sus textos relevantes
        step_items = driver.find_elements(By.CSS_SELECTOR, ".workoutStructureText .stepList li")
        for li in step_items:
            txt = (li.text or "").strip()
            if txt:
                workout_details["steps"].append(txt)
    except Exception:
        pass

    result = {
        "planned_completed": planned_completed,
        "min_avg_max": min_avg_max,
        "description": description,
        "attachments": attachments,
        "workout_details": workout_details,
    }

    print("Datos de workout extraídos ✅")
    return result


def click_cancel_button(timeout=10):
    """
    Hace clic en el botón 'Cancel' (id='discard', class='tpSecondaryButton').

    Retorna:
      True  -> si el clic fue exitoso
      False -> si no se encontró o no fue clickeable
    """
    driver = get_driver()
    
    try:
        cancel_button = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.ID, "discard"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cancel_button)
        try:
            cancel_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", cancel_button)

        print("Botón 'Cancel' clickeado correctamente ✅")
        return True

    except Exception as e:
        print(f"No se pudo hacer clic en el botón 'Cancel': {e}")
        return False


def list_workouts_in_library(library_name, exact=True, timeout=15):
    """
    Lista todos los workouts en una carpeta determinada.
    (Esta función no está en el notebook pero la mantenemos para compatibilidad)
    """
    from .folder_service import click_workout_folder
    
    driver = get_driver()
    
    # 1) Asegura que el panel de libraries está abierto
    if not is_workout_library_open():
        workout_library()

    # 2) Localizar el contenedor de la carpeta (folder) por nombre
    if exact:
        cond = "(normalize-space()='{t}' or @data-tooltip='{t}')".format(t=library_name)
    else:
        cond = "(contains(normalize-space(), '{t}') or contains(@data-tooltip, '{t}'))".format(t=library_name)

    root_xpath = (
        "//div[@id='wrapper']//div[contains(@class,'appContainerLibrayAndContentContainer')]"
        "//div[contains(@class,'libraries') and contains(@class,'open')]"
        "//div[contains(@class,'workoutLibraryFoldersContainer') and contains(@class,'libraryContents')]"
    )

    title_xpath = root_xpath + "//div[contains(@class,'titleContain') and {cond}]".format(cond=cond)

    try:
        title_el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, title_xpath))
        )
    except TimeoutException:
        return []

    # Subimos al contenedor de la carpeta (folder)
    try:
        folder_el = title_el.find_element(
            By.XPATH,
            "ancestor::div[contains(@class,'workoutLibraryFolder')][1]"
        )
    except NoSuchElementException:
        return []

    # 3) Ver si la carpeta está expandida; si no, la expandimos
    classes = (folder_el.get_attribute("class") or "").split()
    if "expanded" not in classes:
        click_workout_folder(library_name, exact=exact)
        # Re-localizamos el folder ya expandido
        title_el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, title_xpath))
        )
        folder_el = title_el.find_element(
            By.XPATH,
            "ancestor::div[contains(@class,'workoutLibraryFolder')][1]"
        )

    # 4) Localizar el contenedor de items
    try:
        items_container = folder_el.find_element(By.CSS_SELECTOR, "div.itemsContainer")
    except NoSuchElementException:
        return []

    # 5) Buscar cada workout dentro del itemsContainer
    workouts = []
    items = items_container.find_elements(By.CSS_SELECTOR, "div.workoutLibraryItem")

    for item in items:
        try:
            # Buscar el título del workout
            name_el_candidates = item.find_elements(By.CSS_SELECTOR, "p.title")
            
            if name_el_candidates:
                name_text = name_el_candidates[0].text.strip()
            else:
                name_el_candidates = item.find_elements(
                    By.CSS_SELECTOR,
                    ".workoutLibraryItemName, .titleContain"
                )
                if name_el_candidates:
                    name_text = name_el_candidates[0].text.strip()
                else:
                    full_text = (item.text or "").strip()
                    name_text = full_text.split('\n')[0].strip() if full_text else ""

            # Solo añadir si el texto no está vacío y no es una métrica
            if name_text and not name_text.startswith('--'):
                workouts.append(name_text)
        except Exception:
            continue

    return workouts

