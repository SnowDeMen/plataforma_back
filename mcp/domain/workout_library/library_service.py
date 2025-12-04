"""
Library Service - Servicios básicos de la Workout Library
"""

from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from ..core import get_driver, get_wait


def click_workout_library():
    """
    Abre el slider de Workout Library.
    """
    driver = get_driver()
    wait = get_wait()
    workout_library_button = wait.until(EC.element_to_be_clickable((By.ID, "exerciseLibrary")))
    workout_library_button.click()


def is_workout_library_open(timeout=0, visible_only=True):
    """
    Verifica si la Workout Library está abierta.
    True  -> existe (y opcionalmente visible) un .workoutLibraryMainComponent
    False -> no existe / no visible.

    timeout: segundos para esperar (0 = chequeo inmediato)
    visible_only: si True, exige que al menos un componente esté visible.
    """
    driver = get_driver()
    selector = ".activeLibraryContainer .workoutLibraryMainComponent[data_cy='workoutLibraryContainer']"
    try:
        if timeout and timeout > 0:
            root = WebDriverWait(driver, timeout).until(
            )
            return (root.is_displayed() if visible_only else True)
        else:
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            if not els:
                return False
            return any(e.is_displayed() for e in els) if visible_only else True
    except Exception:
        return False


def is_library_expanded_by_name(library_name, exact=True):
    """
    Revisa si la Workout Library con el nombre dado está expandida (abierta).
    
    Parámetros:
        library_name (str): nombre de la carpeta a buscar
        exact (bool): True para match exacto, False para match parcial (contains)
    
    Retorna:
      True  -> si la carpeta está expandida
      False -> si existe pero está colapsada
      None  -> si no se encontró la library o si el panel de libraries no está abierto
    """
    driver = get_driver()
    wait = get_wait()
    
    try:
        # Asegura que el panel de libraries esté abierto
        libraries = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "#wrapper > div > div > div.appContainerLibrayAndContentContainer > div.libraries.open"
        )))
    except Exception:
        print("El panel de Workout Libraries no está abierto (no se encontró .libraries.open).")
        return None

    try:
        # Contenedor donde viven las folders
        container = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "#wrapper > div > div > div.appContainerLibrayAndContentContainer > div.libraries.open > div.activeLibraryContainer > div > div.workoutLibraryFoldersContainer.libraryContents"
        )))
    except Exception as e:
        print(f"No se encontró el contenedor de libraries: {e}")
        return None

    # Busca todos los títulos de folders visibles
    title_els = container.find_elements(By.CSS_SELECTOR, ".groupTitle .titleContain")
    target = library_name.strip().lower()

    for title_el in title_els:
        name = (title_el.text or "").strip()
        
        # Aplicar lógica de match según el parámetro exact
        match = False
        if exact:
            match = (name.lower() == target)
        else:
            match = (target in name.lower())
        
        if match:
            # Sube al contenedor de la carpeta
            try:
                folder_el = title_el.find_element(
                    By.XPATH,
                    ".//ancestor::div[contains(@class,'workoutLibraryFolder')][1]"
                )
            except Exception:
                try:
                    folder_el = title_el.find_element(
                        By.XPATH,
                        ".//ancestor::div[contains(@class,'workoutLibraryMainComponent')][1]"
                    )
                except Exception:
                    print(f"Se encontró '{name}', pero no se ubicó el contenedor de folder.")
                    return None

            classes = folder_el.get_attribute("class") or ""
            if "expanded" in classes.split():
                print(f"'{name}' está ABIERTO ✅")
                return True
            else:
                print(f"'{name}' está CERRADO ❌")
                return False

    print(f"No se encontró ninguna Workout Library con nombre '{library_name}' (exact={exact}).")
    return None


def workout_library():
    """
    Asegura que estás en el panel de Workout Library.
    Si no está activo, hace click en la pestaña correspondiente.
    Retorna un mensaje indicando la acción realizada.
    """
    was_open = is_workout_library_open()
    
    if not was_open:
        print("Abriendo Workout Library...")
        click_workout_library()
    else:
        print("Workout Library ya estaba abierta")
    
    # Validar que el panel esté abierto
    if not is_workout_library_open():
        raise TimeoutException("No se pudo abrir el panel de Workout Library.")
    
    return "opened" if not was_open else "already_open"