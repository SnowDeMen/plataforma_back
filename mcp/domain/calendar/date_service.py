"""
Date Service - Servicios de gestión de fechas y drag & drop
"""

import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ActionChains
from ..core import get_driver, get_wait
from .navigation_service import (
    _norm_date,
    _monday_of,
    _week_inview_monday,
    _wait_week_change,
    _ensure_day_visible,
    calendar_go_to_today,
    week_forward,
    week_backward
)


# =============== Validación de drop (calendar) ===============
def _day_contains_workout_title(day_el, workout_title: str) -> bool:
    """
    Verifica si dentro de un dayContainer existe un workout cuyo título coincida.

    Nota:
    - La UI de TrainingPeaks cambia, por eso usamos varios selectores y match flexible.
    - Para títulos largos, el calendario puede truncar visualmente, así que validamos por prefijo.
    """
    raw_title = (workout_title or "").strip()
    if not raw_title:
        return False

    # Prefijo estable para tolerar truncamiento visual
    title_key = raw_title[:28]

    selectors = [
        ".activities .activity.workout h6.newActivityUItitle",
        ".activities .activity.workout h6",
        ".activities .activity.workout .newActivityUItitle",
    ]

    for sel in selectors:
        try:
            els = day_el.find_elements(By.CSS_SELECTOR, sel)
        except Exception:
            continue
        for el in els:
            try:
                txt = (el.text or "").strip()
            except Exception:
                continue
            if not txt:
                continue
            if txt == raw_title:
                return True
            if title_key and title_key in txt:
                return True
    return False


def _wait_drop_visible(
    *,
    target_date,
    workout_title: str,
    timeout: int = 10,
    use_today: bool = True,
):
    """
    Espera a que el workout (por título) aparezca en el día objetivo del calendario.

    Si no aparece dentro del timeout, levanta TimeoutException.
    """
    driver = get_driver()

    def _cond(_):
        try:
            day_el = _ensure_day_visible(target_date, use_today=use_today)
        except Exception:
            return False
        try:
            return _day_contains_workout_title(day_el, workout_title)
        except Exception:
            return False

    WebDriverWait(driver, timeout).until(_cond)


def _collapse_other_folders(target_folder: str) -> None:
    """
    Colapsa todas las carpetas expandidas de Workout Library que NO sean la carpeta objetivo.
    
    Esto evita que el workout recién creado se encuentre en "Recents" u otras carpetas
    en lugar de la carpeta correcta.
    """
    driver = get_driver()
    target = (target_folder or "").strip()
    
    # Buscar todas las carpetas actualmente expandidas
    expanded_folders = driver.find_elements(
        By.XPATH,
        "//div[contains(@class,'workoutLibraryFolder') and contains(@class,'expanded')]"
    )
    
    for folder_el in expanded_folders:
        try:
            # Obtener el nombre de esta carpeta via data-tooltip
            title_el = folder_el.find_element(By.CSS_SELECTOR, ".titleContain")
            tooltip = (title_el.get_attribute("data-tooltip") or "").strip()
            
            # Si NO es la carpeta objetivo, colapsarla
            if tooltip and tooltip != target:
                header = folder_el.find_element(By.CSS_SELECTOR, ".listHeader")
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", header)
                try:
                    header.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", header)
                # Pausa breve para que la UI se actualice
                time.sleep(0.3)
        except Exception:
            # Si falla colapsar una carpeta, continuar con las demás
            continue


def _ensure_workout_library_folder_open(folder: str, timeout: int = 12) -> None:
    """
    Asegura que un folder específico de Workout Library esté EXPANDIDO.

    Estrategia:
    1. Colapsar TODAS las carpetas que no sean la objetivo (evita encontrar workout en Recents).
    2. Localizar el div.workoutLibraryFolder que contiene un titleContain con data-tooltip igual al folder.
    3. Si no tiene clase 'expanded', hacer click en listHeader o expander.
    4. Esperar a que el contenedor tenga clase 'expanded'.
    """
    driver = get_driver()
    wait = get_wait()

    target = (folder or "").strip()
    if not target:
        return

    # Paso 1: Colapsar otras carpetas para evitar encontrar el workout en Recents
    _collapse_other_folders(target)

    # Paso 2: XPath robusto con hijo directo listHeader para evitar match anidado
    folder_xpath = (
        "//div[contains(@class,'workoutLibraryFolder')]"
        f"[./div[contains(@class,'listHeader')]//div[contains(@class,'titleContain') and @data-tooltip='{target}']]"
    )

    folder_el = wait.until(EC.presence_of_element_located((By.XPATH, folder_xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", folder_el)

    def _is_expanded() -> bool:
        try:
            classes = (folder_el.get_attribute("class") or "").split()
            return "expanded" in classes
        except Exception:
            return False

    if _is_expanded():
        return

    # Paso 3: Click para expandir
    click_selectors = [
        ".listHeader",
        ".listHeader .toggleArea",
        ".listHeader .expander",
    ]
    last_err = None
    for sel in click_selectors:
        try:
            el = folder_el.find_element(By.CSS_SELECTOR, sel)
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            # Esperar a que el contenedor quede expandido
            WebDriverWait(driver, timeout).until(lambda d: _is_expanded())
            return
        except Exception as e:
            last_err = e
            continue

    raise TimeoutException(f"No se pudo expandir el folder '{target}'. Último error: {last_err}")


# ---------- FUNCIÓN PRINCIPAL: sin límite práctico ----------
def click_calendar_date_until(target_date, use_today=True, max_weeks=1040, per_step_timeout=5.0, retry_clicks=3):
    """
    Usa SOLO week_forward()/week_backward() (y opcionalmente calendar_go_to_today())
    hasta llegar a la semana objetivo; luego clickea EXCLUSIVAMENTE el dayContainer exacto.

    - target_date: 'YYYY-MM-DD' | datetime.date | datetime.datetime
    - use_today:   si True, primero presiona 'Go to Today' para partir de estado conocido
    - max_weeks:   límite duro para evitar loops infinitos (1040 ≈ 20 años)
    - per_step_timeout: espera por cambio de semana en cada click
    - retry_clicks: reintentos si el click no cambia la semana
    """
    driver = get_driver()
    wait = get_wait()
    
    d, date_str, monday_str = _norm_date(target_date)
    target_monday = _monday_of(d)

    # 1) reubicar en "Hoy" (opcional pero recomendable)
    if use_today:
        calendar_go_to_today()
        # si no había inView, espera a que exista
        try:
            _wait_week_change(prev_monday=None, timeout=per_step_timeout)
        except TimeoutException:
            pass

    # 2) leer semana visible actual
    cur_monday = _week_inview_monday()
    if not cur_monday:
        raise TimeoutException("No pude determinar la semana visible del calendario.")

    steps = 0
    while steps < max_weeks:
        # ¿ya llegamos?
        if _monday_of(cur_monday) == target_monday:
            break

        # decidir dirección según diferencia
        diff_weeks = (target_monday - cur_monday).days // 7
        go_forward = diff_weeks > 0

        # click + espera de cambio (con reintentos si la semana no cambia)
        changed = False
        for _ in range(retry_clicks):
            last = cur_monday
            if go_forward:
                week_forward()
            else:
                week_backward()
            try:
                cur_monday = _wait_week_change(prev_monday=last, timeout=per_step_timeout)
                changed = True
                break
            except TimeoutException:
                # reintento: a veces el primer click no toma
                time.sleep(0.1)
                continue

        if not changed:
            # Si tras varios intentos no cambia, probamos invertir (por si diff estaba desfasado)
            go_forward = not go_forward
            for _ in range(retry_clicks):
                last = cur_monday
                if go_forward:
                    week_forward()
                else:
                    week_backward()
                try:
                    cur_monday = _wait_week_change(prev_monday=last, timeout=per_step_timeout)
                    changed = True
                    break
                except TimeoutException:
                    time.sleep(0.1)
                    continue

        if not changed:
            raise TimeoutException("No hubo cambio de semana tras múltiples clicks de navegación.")

        steps += 1

    if _monday_of(cur_monday) != target_monday:
        raise TimeoutException(f"No se alcanzó la semana {monday_str} tras {steps} pasos (semana actual: {cur_monday}).")

    # 3) Click EXACTO al día dentro de la semana objetivo
    day_css = (
        f"div[data_cy='calendarWeekContainer'][data-date='{monday_str}'] "
        f".daysContainer div[data_cy='dayContainer'][data-date='{date_str}']"
    )
    day = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, day_css)))
    try:
        day.click()
    except Exception:
        driver.execute_script("arguments[0].click();", day)


# =============== Localizador del workout por título ===============
def _find_workout_tile(title, folder=None, exact=False, timeout=12):
    """
    Devuelve el contenedor draggable del workout a partir de su <p class='title'>.
    
    Estrategia:
    - Si 'folder' se da, primero colapsa otras carpetas y expande solo ese folder.
    - Usa XPath con hijo directo listHeader para evitar match en carpetas anidadas.
    - Si hay múltiples workouts con el mismo título, toma el de mayor data-exerciseid
      (el más reciente agregado).
    - Devuelve el div.workoutLibraryItem[draggable=true] que es el elemento arrastrable.
    """
    driver = get_driver()
    wait = get_wait()
    
    if folder:
        # Asegurar que SOLO el folder objetivo esté expandido (colapsa otros)
        _ensure_workout_library_folder_open(folder, timeout=timeout)
        # XPath específico: usa ./div para hijo directo listHeader, evita match anidado
        container_xpath = (
            "//div[contains(@class,'workoutLibraryFolder')]"
            f"[./div[contains(@class,'listHeader')]//div[contains(@class,'titleContain') and @data-tooltip='{folder}']]"
        )
    else:
        container_xpath = ""

    pred = f"normalize-space()='{title}'" if exact else f"contains(normalize-space(), '{title}')"
    xp_title = f"{container_xpath}//p[contains(@class,'title') and {pred}]"

    # Esperar a que exista al menos un match
    wait.until(EC.presence_of_element_located((By.XPATH, xp_title)))
    
    # Buscar TODOS los matches para poder elegir el más reciente
    all_title_els = driver.find_elements(By.XPATH, xp_title)
    
    if not all_title_els:
        raise TimeoutException(f"No se encontró workout con título '{title}'")
    
    # Función auxiliar para obtener el exerciseid del tile padre
    def _get_exercise_id(title_el):
        try:
            tile = title_el.find_element(
                By.XPATH,
                "ancestor::div[contains(@class,'workoutLibraryWorkoutTile')]"
            )
            eid = tile.get_attribute("data-exerciseid")
            return int(eid) if eid else 0
        except Exception:
            return 0
    
    # Si hay múltiples matches, ordenar por exerciseid descendente (el mayor es el más reciente)
    if len(all_title_els) > 1:
        all_title_els.sort(key=_get_exercise_id, reverse=True)
    
    title_el = all_title_els[0]
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", title_el)

    # Preferimos el contenedor draggable (workoutLibraryItem con draggable=true)
    draggable_xpaths = [
        "ancestor::div[contains(@class,'workoutLibraryItem') and @draggable='true']",
        "ancestor::div[contains(@class,'workoutLibraryItem')]",
        "ancestor::div[contains(@class,'workoutLibraryWorkoutTile')]",
    ]
    for rel in draggable_xpaths:
        els = title_el.find_elements(By.XPATH, rel)
        if els:
            return els[0]
    return title_el  # fallback: el título

# =============== Drag & Drop principal ===============
def drag_workout_to_calendar(workout_title, target_date, folder=None, exact_title=False, use_today=True):
    """
    Arrastra el workout identificado por 'workout_title' y lo suelta en 'target_date' (YYYY-MM-DD | date | datetime).
    - Usa solo tus botones para montar la semana correcta.
    - Drop robusto: ActionChains -> ActionChains+offset -> JS HTML5 (DataTransfer).
    """
    driver = get_driver()
    
    src = _find_workout_tile(workout_title, folder=folder, exact=exact_title)
    dst = _ensure_day_visible(target_date, use_today=use_today)

    # Traer ambos a vista
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", src)
    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", dst)

    # 1) Intento estándar
    try:
        ActionChains(driver).click_and_hold(src).pause(0.2).move_to_element(dst).pause(0.2).release().perform()
        _wait_drop_visible(target_date=target_date, workout_title=workout_title, timeout=10, use_today=False)
        return
    except Exception:
        pass

    # 2) Intento con offset al centro del día (algunas UIs requieren caer dentro del grid)
    try:
        size = dst.size
        cx, cy = int(size['width'] * 0.5), int(size['height'] * 0.5)
        ActionChains(driver).click_and_hold(src).pause(0.2)\
            .move_to_element_with_offset(dst, cx, cy).pause(0.2).release().perform()
        _wait_drop_visible(target_date=target_date, workout_title=workout_title, timeout=10, use_today=False)
        return
    except Exception:
        pass

    # 3) HTML5 drag & drop por JS (para apps que no aceptan el drag nativo de Selenium)
    js = """
    function html5DragAndDrop(src, dst) {
      const dataTransfer = new DataTransfer();
      function fire(el, type){
        const e = new DragEvent(type, {bubbles:true, cancelable:true, dataTransfer});
        el.dispatchEvent(e);
      }
      fire(src, 'dragstart');
      fire(dst, 'dragenter');
      fire(dst, 'dragover');
      fire(dst, 'drop');
      fire(src, 'dragend');
    }
    html5DragAndDrop(arguments[0], arguments[1]);
    """
    driver.execute_script(js, src, dst)
    
    # Validación final: si este método no funcionó, aquí sí queremos un error claro.
    _wait_drop_visible(target_date=target_date, workout_title=workout_title, timeout=12, use_today=False)

