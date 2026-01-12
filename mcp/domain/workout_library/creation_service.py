"""
Creation Service - Servicios de creacion de workouts directamente en la plataforma

Este modulo contiene funciones para crear entrenamientos desde cero
en TrainingPeaks sin necesidad de archivos ZWO.
"""

import time
from typing import Dict, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    StaleElementReferenceException,
)
from ..core import get_driver, get_wait
from .library_service import workout_library
from .folder_service import folder_settings


def click_create_workout(timeout: int = 10, scope=None) -> bool:
    """
    Hace clic en el boton 'Create Workout' dentro de la Workout Library.

    Args:
        timeout: Segundos maximos de espera.
        scope: WebElement raiz opcional para acotar la busqueda.

    Returns:
        True si el clic se realizo correctamente.

    Raises:
        TimeoutException: Si no aparece el elemento en el tiempo especificado.
    """
    driver = get_driver()
    selector = "label.addOption[data_cy='addWorkout']"

    # Esperar a que exista y sea clickeable
    el = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
    )

    # Llevar a vista y hacer clic (fallback JS si el click normal falla)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)

    return True


def set_workout_title(title: str, timeout: int = 10, scope=None) -> bool:
    """
    Escribe el nombre del workout en el textbox de 'Workout Title'.

    Args:
        title: Texto a escribir como titulo del workout.
        timeout: Segundos maximos de espera.
        scope: WebElement opcional para buscar localmente.

    Returns:
        True si se escribio exitosamente.

    Raises:
        Exception: Si no se encuentra el textbox de titulo.
    """
    driver = get_driver()

    # Selectores posibles (TrainingPeaks cambia IDs dinamicamente)
    selectors = [
        "input[placeholder='Workout Title']",
        "input.MuiInputBase-input.MuiFilledInput-input",
        "input[type='text'][aria-invalid]"
    ]

    input_el = None

    # Buscar el elemento usando varios selectores
    for sel in selectors:
        try:
            input_el = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            break
        except Exception:
            continue

    if input_el is None:
        raise Exception("No se encontro el textbox de 'Workout Title'.")

    # Scroll al elemento
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", input_el)
    except Exception:
        pass

    # Intento de focus
    try:
        input_el.click()
    except Exception:
        driver.execute_script("arguments[0].focus();", input_el)

    # Limpiar texto previo
    try:
        input_el.clear()
    except Exception:
        driver.execute_script("arguments[0].value='';", input_el)

    # Escribir texto
    try:
        input_el.send_keys(title)
    except Exception:
        driver.execute_script(f"arguments[0].value='{title}';", input_el)

    return True


def click_add_button(timeout: int = 10) -> bool:
    """
    Da click al boton 'Add' dentro del modal de crear workout.
    Usa selectores multiples ya que MUI genera clases dinamicas.

    Args:
        timeout: Segundos maximos de espera.

    Returns:
        True si se hizo clic correctamente.

    Raises:
        TimeoutException: Si no se encuentra el boton.
        Exception: Si no se pudo hacer clic.
    """
    driver = get_driver()

    selectors = [
        # Por texto exacto dentro de un boton
        "//button[normalize-space()='Add']",
        "//button[contains(., 'Add')]",
        # Por clases tipicas de MUI para botones primarios
        "//button[contains(@class, 'MuiButton-containedPrimary')]",
        # Por type=button dentro de un modal MUI
        "//button[@type='button' and contains(@class,'MuiButton')]"
    ]

    add_btn = None

    # Buscar el boton usando multiples selectores
    for xp in selectors:
        try:
            add_btn = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            break
        except Exception:
            continue

    if not add_btn:
        raise TimeoutException("No se encontro el boton 'Add'.")

    # Scroll al elemento
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", add_btn)
    except Exception:
        pass

    # Secuencia robusta de click
    try:
        add_btn.click()
        return True
    except Exception:
        pass

    try:
        ActionChains(driver).move_to_element(add_btn).pause(0.05).click().perform()
        return True
    except Exception:
        pass

    try:
        driver.execute_script("arguments[0].click();", add_btn)
        return True
    except Exception:
        pass

    raise Exception("No se pudo hacer click en el boton 'Add'.")


def click_workout_type_option(option_name: str, timeout: int = 10, exact: bool = False) -> bool:
    """
    Da click a uno de los botones de tipo de workout en el modal de creacion.
    
    Args:
        option_name: Texto del boton (Run, Bike, Swim, Strength, etc.).
        timeout: Segundos maximos de espera.
        exact: True para match exacto, False para contains.

    Returns:
        True si se hizo clic correctamente.

    Raises:
        TimeoutException: Si no se encuentra la opcion.
        Exception: Si no se pudo hacer clic.
    """
    driver = get_driver()

    # XPath que busca el <p> por nombre
    if exact:
        pred = f"normalize-space()='{option_name}'"
    else:
        pred = f"contains(normalize-space(), '{option_name}')"

    xpath = f"//p[contains(@class,'MuiTypography-root') and {pred}]"

    try:
        el = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except TimeoutException:
        raise TimeoutException(f"No se encontro la opcion '{option_name}' en el modal.")

    # Scroll
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass

    # Intento de click normal
    try:
        WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        el.click()
        return True
    except Exception:
        pass

    # Intento con Actions
    try:
        ActionChains(driver).move_to_element(el).pause(0.05).click().perform()
        return True
    except Exception:
        pass

    # Ultimo recurso: JavaScript
    try:
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        pass

    raise Exception(f"No se pudo hacer clic en la opcion '{option_name}'.")


def click_strength_modal_button(timeout: int = 10) -> bool:
    """
    Hace click en el boton de confirmacion del modal que aparece
    al seleccionar Strength como tipo de workout.

    TrainingPeaks muestra un modal adicional para workouts de fuerza
    que requiere confirmacion antes de continuar con la creacion.

    Args:
        timeout: Segundos maximos de espera para el boton.

    Returns:
        True si el click se realizo correctamente.

    Raises:
        TimeoutException: Si el boton no aparece en el tiempo especificado.
    """
    driver = get_driver()

    selector = "button.MuiButton-outlinedPrimary"

    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)

    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)

    return True


def set_workout_description(text: str, timeout: int = 10, clear_first: bool = True) -> None:
    """
    Escribe en el campo Description (div#descriptionInput, contenteditable).

    Args:
        text: Texto a escribir en la descripcion.
        timeout: Segundos de espera maxima.
        clear_first: Si True, limpia el contenido antes de escribir.
    """
    driver = get_driver()

    # Esperar a que exista y sea visible
    desc = WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.ID, "descriptionInput"))
    )

    # Llevar a vista y dar foco
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", desc)
    desc.click()

    if clear_first:
        # Ctrl+A + Delete para limpiar
        desc.send_keys(Keys.CONTROL + "a")
        desc.send_keys(Keys.DELETE)

    if text:
        desc.send_keys(text)


def set_pre_activity_comments(text: str, timeout: int = 10, retries: int = 2) -> None:
    """
    Escribe el texto en el campo 'Pre-Activity Comments' del modal de workout.

    Usa el div contenteditable con id='preActivityCommentsInput'.

    Args:
        text: Texto a escribir en los comentarios.
        timeout: Segundos de espera maxima.
        retries: Numero de reintentos si el elemento se vuelve stale.

    Raises:
        RuntimeError: Si no se pueden asignar los comentarios despues de los reintentos.
    """
    driver = get_driver()
    locator = (By.ID, "preActivityCommentsInput")

    last_exception = None

    for attempt in range(retries + 1):
        try:
            # Esperar a que el editor exista y sea interactuable
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )

            # Asegurar foco
            try:
                driver.execute_script("arguments[0].focus();", el)
            except Exception:
                pass

            # Limpiar el contenido actual (por ser contenteditable, clear() no sirve)
            driver.execute_script("arguments[0].innerHTML = '';", el)

            # Click y escribir
            el.click()
            if text:
                el.send_keys(text)

            # Si todo salio bien, salimos de la funcion
            return

        except StaleElementReferenceException as e:
            last_exception = e
            continue
        except TimeoutException as e:
            last_exception = e
            break
        except Exception as e:
            last_exception = e
            break

    raise RuntimeError(
        f"No se pudieron asignar los pre-activity comments despues de varios intentos: {last_exception}"
    )


def click_save_button(timeout: int = 10, retries: int = 2) -> str:
    """
    Hace click en el boton 'Save & Close' del modal de workout.

    HTML objetivo:
        <button id="close" class="tpPrimaryButton" data_cy="Save&Close">Save & Close</button>

    Args:
        timeout: Segundos maximos de espera.
        retries: Numero de reintentos.

    Returns:
        Mensaje indicando el resultado de la operacion.
    """
    driver = get_driver()
    wait = get_wait()
    locator = (By.ID, "close")
    last_exception = None

    for attempt in range(retries + 1):
        try:
            # Esperar a que el boton exista y sea clickeable
            btn = wait.until(
                EC.element_to_be_clickable(locator)
            )

            # Intento normal
            try:
                btn.click()
            except Exception:
                # Forzar click por JS si el normal falla
                driver.execute_script("arguments[0].click();", btn)

            return "[OK] Save & Close clickeado"

        except Exception as e:
            last_exception = e
            continue

    return f"[ERROR] No se pudo clickear el boton Save & Close: {str(last_exception)}"


def get_workout_modal_input_parameters(
    timeout: int = 10, 
    include_hidden: bool = False, 
    include_disabled: bool = False
) -> Optional[Dict]:
    """
    Lee el modal de workout y devuelve:
      - workout_title (ej. "Test")
      - workout_type (ej. "Swim", "Run", etc.)
      - lista de parametros inputables de la seccion #workoutPlannedCompletedStats

    Args:
        timeout: Segundos maximos de espera.
        include_hidden: Si True, incluye filas con clase 'hide'.
        include_disabled: Si True, incluye tambien inputs deshabilitados.

    Returns:
        Dict con titulo, tipo y parametros del modal, o None si falla.
        {
            "workout_title": str | None,
            "workout_type": str | None,
            "parameters": [
                {
                    "name": str | None,
                    "planned_input_id": str | None,
                    "units": str | None,
                    "planned_input_disabled": bool,
                    "row_classes": [str, ...]
                },
                ...
            ]
        }
    """
    driver = get_driver()

    def _safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    # Asegurar que exista el contenedor de stats del workout
    try:
        stats_root = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "workoutPlannedCompletedStats"))
        )
    except TimeoutException:
        print("No se encontro #workoutPlannedCompletedStats.")
        return None

    # Obtener el titulo del workout (input.title.workoutTitle)
    workout_title = None
    title_input = _safe(lambda: driver.find_element(
        By.CSS_SELECTOR,
        "input.title.workoutTitle"
    ))
    if title_input:
        workout_title = (title_input.get_attribute("value") or "").strip()
        if not workout_title:
            # fallback al placeholder si no hay valor
            workout_title = (title_input.get_attribute("placeholder") or "").strip() or None

    # Obtener el tipo de workout (Run, Bike, Swim, etc.)
    workout_type = None
    try:
        type_candidates = driver.find_elements(
            By.CSS_SELECTOR,
            "div.MuiStack-root h6.MuiTypography-subtitle2.MuiTypography-noWrap"
        )
        for el in type_candidates:
            text = (el.text or "").strip()
            if text:
                workout_type = text
                break
    except Exception:
        pass

    # Recorrer todas las filas de stats (Planned / Completed)
    params = []
    rows = stats_root.find_elements(By.CSS_SELECTOR, ".workoutStatsRow")

    for row in rows:
        row_classes = (row.get_attribute("class") or "").split()

        # Filtramos filas ocultas (clase 'hide') si no queremos hidden
        if not include_hidden and "hide" in row_classes:
            continue

        # Label del parametro
        label_el = _safe(lambda: row.find_element(
            By.CSS_SELECTOR,
            ".workoutStatsColumn.workoutStatsLabel label"
        ))
        name = (label_el.text.strip() if label_el and label_el.text else None)

        # Input Planned
        planned_input = _safe(lambda: row.find_element(
            By.CSS_SELECTOR,
            ".workoutStatsColumn.workoutStatsPlanned input"
        ))
        if not planned_input:
            continue

        # Checar si esta disabled
        is_disabled_attr = planned_input.get_attribute("disabled")
        is_disabled_prop = _safe(lambda: planned_input.get_property("disabled"), False)
        is_disabled = bool(is_disabled_attr) or bool(is_disabled_prop)

        if (not include_disabled) and is_disabled:
            continue

        input_id = planned_input.get_attribute("id") or None

        # Units (si existen)
        units_label_el = _safe(lambda: row.find_element(
            By.CSS_SELECTOR,
            ".workoutStatsColumn.workoutStatsUnitLabel label"
        ))
        units = (units_label_el.text.strip() if units_label_el and units_label_el.text else None)

        params.append({
            "name": name,
            "planned_input_id": input_id,
            "units": units,
            "planned_input_disabled": is_disabled,
            "row_classes": row_classes,
        })

    result = {
        "workout_title": workout_title,
        "workout_type": workout_type,
        "parameters": params,
    }

    print("Titulo, tipo y parametros inputables del modal extraidos.")
    return result


def create_workout(
    folder_name: Optional[str] = None,
    workout_type: str = "Run",
    title: Optional[str] = None,
    description: Optional[str] = None,
    pre_activity_comments: Optional[str] = None,
    planned_values: Optional[Dict[str, str]] = None,
    click_save: bool = True,
    timeout: int = 15,
) -> str:
    """
    Crea un workout dentro de la Workout Library aplicando titulo, tipo,
    descripcion, comentarios y parametros planeados.

    Args:
        folder_name: Carpeta destino dentro de la Workout Library (opcional).
        workout_type: Tipo de workout (Run, Bike, Swim, etc.).
        title: Titulo del workout.
        description: Descripcion del workout.
        pre_activity_comments: Comentarios previos a la actividad.
        planned_values: Diccionario con parametros (Duration, Distance, TSS, IF, etc.).
        click_save: Si True, confirma el modal con el boton Save & Close.
        timeout: Timeout para operaciones internas.

    Returns:
        Mensaje indicando exito o error.
    """
    wait = get_wait()

    try:
        # Asegurar que estamos en Workout Library
        try:
            workout_library()
        except Exception as e:
            return f"[ERROR] No se pudo abrir Workout Library: {str(e)}"

        # Opcional: abrir settings de la carpeta
        if folder_name:
            try:
                folder_settings(folder_name)
            except Exception as e:
                return f"[ERROR] No se pudo abrir settings de la carpeta '{folder_name}': {str(e)}"

        # Abrir modal de creacion
        try:
            click_create_workout()
        except Exception as e:
            return f"[ERROR] No se pudo abrir el modal de creacion de workout: {str(e)}"
        
        # Titulo
        if title:
            try:
                set_workout_title(title)
            except Exception as e:
                return f"[ERROR] No se pudo asignar el titulo: {str(e)}"

        # Add (confirmar titulo)
        if title:
            try:
                click_add_button()
            except Exception as e:
                return f"[ERROR] No se pudo dar click al boton Add: {str(e)}"

        # Seleccionar tipo
        try:
            click_workout_type_option(workout_type)
        except Exception as e:
            return f"[ERROR] No se pudo seleccionar el tipo de workout '{workout_type}': {str(e)}"

        # Para Strength: confirmar modal adicional de TrainingPeaks
        if workout_type.lower() == "strength":
            try:
                click_strength_modal_button()
            except Exception as e:
                return f"[ERROR] No se pudo confirmar el modal de Strength: {str(e)}"

        # Descripcion
        if description is not None:
            try:
                set_workout_description(description)
            except Exception as e:
                return f"[ERROR] No se pudo asignar la descripcion: {str(e)}"

        # Comentarios previos
        if pre_activity_comments is not None:
            try:
                set_pre_activity_comments(pre_activity_comments)
            except Exception as e:
                return f"[ERROR] No se pudieron asignar los pre-activity comments: {str(e)}"

        # Parametros del modal
        try:
            modal_info = get_workout_modal_input_parameters(timeout=timeout)
        except Exception as e:
            return f"[ERROR] No se pudieron obtener los parametros del modal: {str(e)}"

        parameters = modal_info.get("parameters", []) if modal_info else []
        params_by_name = {
            p.get("name"): p
            for p in parameters
            if p.get("name")
        }

        # Asignar valores planeados
        if planned_values:
            for name, value in planned_values.items():

                if name not in params_by_name:
                    return f"[ERROR] El parametro '{name}' no esta disponible para este tipo de workout"

                param = params_by_name[name]
                input_id = param.get("planned_input_id")
                disabled = param.get("planned_input_disabled", False)

                if not input_id:
                    return f"[ERROR] El parametro '{name}' no tiene planned_input_id definido"

                if disabled:
                    return f"[ERROR] El parametro '{name}' esta deshabilitado en este contexto"

                try:
                    el = wait.until(
                        EC.element_to_be_clickable((By.ID, input_id))
                    )
                    el.clear()
                    el.send_keys(str(value))
                except Exception as e:
                    return f"[ERROR] No se pudo asignar '{name}' (id={input_id}): {str(e)}"

        # Click en Save
        if click_save:
            try:
                result = click_save_button()
                if "[ERROR]" in result:
                    return result
            except Exception as e:
                return f"[ERROR] No se pudo confirmar con el boton Save: {str(e)}"

        return "[OK] Workout creado correctamente"

    except Exception as e:
        return f"[ERROR] Error inesperado: {str(e)}"

