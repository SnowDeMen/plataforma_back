"""
Date Service - Servicios de gestión de fechas y drag & drop
"""

import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
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
    Si 'folder' se da, limita la búsqueda a ese folder (listHeader -> workoutLibraryFolder).
    """
    driver = get_driver()
    wait = get_wait()
    
    if folder:
        header_xpath = (
            "//div[contains(@class,'titleContain') and "
            f"(normalize-space()='{folder}' or @data-tooltip='{folder}')]"
            "/ancestor::div[contains(@class,'listHeader')]"
        )
        container_xpath = header_xpath + "/ancestor::div[contains(@class,'workoutLibraryFolder')]"
    else:
        container_xpath = ""

    pred = f"normalize-space()='{title}'" if exact else f"contains(normalize-space(), '{title}')"
    xp_title = f"{container_xpath}//p[contains(@class,'title') and {pred}]"

    title_el = wait.until(EC.presence_of_element_located((By.XPATH, xp_title)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", title_el)

    # Preferimos el tile draggable
    for rel in [
        "ancestor::div[contains(@class,'workoutLibraryWorkoutTile')]",  # data_cy='libraryWorkoutTile'
        "ancestor::div[contains(@class,'workoutLibraryItem')]"          # data_cy='libraryItemContainer'
    ]:
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
        return
    except Exception:
        pass

    # 2) Intento con offset al centro del día (algunas UIs requieren caer dentro del grid)
    try:
        size = dst.size
        cx, cy = int(size['width'] * 0.5), int(size['height'] * 0.5)
        ActionChains(driver).click_and_hold(src).pause(0.2)\
            .move_to_element_with_offset(dst, cx, cy).pause(0.2).release().perform()
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

