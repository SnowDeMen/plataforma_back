"""
Navigation Service - Servicios de navegación en el calendario
"""

import time
from datetime import date, datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from ..core import get_driver, get_wait


def week_forward():
    wait = get_wait()
    button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "weekArrowForwardButton")))
    button.click()

def week_backward():
    wait = get_wait()
    button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "weekArrowBackButton")))
    button.click()

def calendar_go_to_today():
    wait = get_wait()
    button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "goToTodayButton")))
    button.click()


# ---------- helpers de fecha ----------
def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _norm_date(target):
    if isinstance(target, datetime):
        d = target.date()
    elif isinstance(target, date):
        d = target
    else:
        d = datetime.fromisoformat(str(target)).date()
    return d, d.strftime("%Y-%m-%d"), _monday_of(d).strftime("%Y-%m-%d")


# ---------- helpers de DOM ----------
def _week_inview_el():
    # Preferimos .inView; si no existe, primera visible
    driver = get_driver()
    els = driver.find_elements(By.CSS_SELECTOR, "div[data_cy='calendarWeekContainer'].inView")
    for e in els:
        if e.is_displayed():
            return e
    vis = [w for w in driver.find_elements(By.CSS_SELECTOR, "div[data_cy='calendarWeekContainer']") if w.is_displayed()]
    return vis[0] if vis else None

def _week_inview_monday():
    el = _week_inview_el()
    if not el:
        return None
    try:
        return datetime.fromisoformat(el.get_attribute("data-date")).date()
    except Exception:
        return None

def _wait_week_change(prev_monday, timeout=6.0):
    """Espera a que cambie el lunes visible respecto a prev_monday (o a que haya uno si prev_monday es None)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        cur = _week_inview_monday()
        if prev_monday is None and cur is not None:
            return cur
        if cur and cur != prev_monday:
            return cur
        time.sleep(0.05)
    raise TimeoutException("La semana visible no cambió después de navegar.")


# =============== Helpers de calendario (solo lectura / navegación por botones) ===============
def _ensure_day_visible(target_date, use_today=True, per_step_timeout=5.0, max_weeks=1040):
    """
    Navega SOLO con tus botones hasta que la semana objetivo esté montada
    y devuelve el elemento del dayContainer exacto.
    """
    driver = get_driver()
    wait = get_wait()
    
    d, date_str, monday_str = _norm_date(target_date)
    target_monday = _monday_of(d)

    if use_today:
        calendar_go_to_today()
        try:
            _wait_week_change(prev_monday=None, timeout=per_step_timeout)
        except TimeoutException:
            pass

    cur_monday = _week_inview_monday()
    if not cur_monday:
        raise TimeoutException("No pude determinar la semana visible del calendario.")

    steps = 0
    while _monday_of(cur_monday) != target_monday and steps < max_weeks:
        diff_weeks = (target_monday - cur_monday).days // 7
        go_forward = diff_weeks > 0

        last = cur_monday
        if go_forward:
            week_forward()
        else:
            week_backward()
        cur_monday = _wait_week_change(prev_monday=last, timeout=per_step_timeout)
        steps += 1

    if _monday_of(cur_monday) != target_monday:
        raise TimeoutException(f"No se alcanzó la semana {monday_str}; actual: {cur_monday}.")

    # ¡Semana correcta montada! devolvemos el contenedor de la fecha exacta
    day_css = (
        f"div[data_cy='calendarWeekContainer'][data-date='{monday_str}'] "
        f".daysContainer div[data_cy='dayContainer'][data-date='{date_str}']"
    )
    day = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, day_css)))
    return day

