"""
Workout Service - Servicios de gestión de workouts en el calendario
"""

import time
from typing import Optional, Dict, Any, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver import ActionChains
from ..core import get_driver
from .navigation_service import _ensure_day_visible


def _truncate_text(value: Optional[str], max_chars: int) -> Optional[str]:
    """
    Trunca texto para evitar payloads gigantes.
    """
    if value is None:
        return None
    if max_chars <= 0:
        return ""
    s = str(value)
    return s if len(s) <= max_chars else (s[:max_chars] + "…(truncado)")


def _safe_collect_clickable_detail_candidates() -> list:
    """
    Intenta encontrar candidatos clickeables dentro del Quick View que lleven
    a la página completa del workout/actividad.
    
    Nota: TrainingPeaks cambia UI frecuentemente, así que usamos heurísticas:
    - texto visible que contenga 'details' / 'detail' / 'ver'
    - href que contenga 'workout'/'activity' o parámetros id
    """
    driver = get_driver()
    candidates = []
    try:
        qv = driver.find_element(By.ID, "quickViewContent")
    except Exception:
        return candidates

    # 1) anchors con href "interesante"
    try:
        links = qv.find_elements(By.CSS_SELECTOR, "a[href]")
        for a in links:
            try:
                href = (a.get_attribute("href") or "").lower()
                txt = (a.text or "").strip().lower()
                if not a.is_displayed():
                    continue
                if any(k in href for k in ["workout", "activity", "workoutid", "activityid", "athleteworkout"]):
                    candidates.append(a)
                    continue
                if "detail" in txt or "details" in txt or "ver" in txt:
                    candidates.append(a)
            except Exception:
                continue
    except Exception:
        pass

    # 2) botones (incluye MUI)
    try:
        btns = qv.find_elements(By.CSS_SELECTOR, "button, [role='button']")
        for b in btns:
            try:
                if not b.is_displayed():
                    continue
                txt = (b.text or "").strip().lower()
                aria = (b.get_attribute("aria-label") or "").strip().lower()
                title = (b.get_attribute("title") or "").strip().lower()
                haystack = " ".join([txt, aria, title])
                if any(k in haystack for k in ["view details", "details", "detail", "ver detalles", "ver detalle"]):
                    candidates.append(b)
            except Exception:
                continue
    except Exception:
        pass

    return candidates


def open_full_workout_details_from_quickview(timeout: int = 12) -> bool:
    """
    Intenta navegar desde el Quick View hacia la página completa del workout/actividad.
    
    Estrategia (preferida por UI click):
    - Busca candidatos clickeables dentro del Quick View con heurísticas.
    - Click y espera a que cambie la URL o desaparezca el Quick View.
    
    Returns:
        True si parece haber navegado a un detalle completo, False si no encontró forma.
    """
    driver = get_driver()
    try:
        before = driver.current_url
    except Exception:
        before = ""

    candidates = _safe_collect_clickable_detail_candidates()
    if not candidates:
        return False

    for el in candidates:
        try:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            except Exception:
                pass

            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)

            # Esperar a que cambie la URL o desaparezca el quickview.
            def _navigated(d):
                try:
                    if before and d.current_url != before:
                        return True
                except Exception:
                    pass
                try:
                    qv = d.find_elements(By.ID, "quickViewContent")
                    if not qv:
                        return True
                except Exception:
                    pass
                return False

            WebDriverWait(driver, timeout).until(_navigated)
            return True
        except Exception:
            continue

    return False


def extract_full_workout_page_visible_details(
    *,
    max_visible_text_chars: int = 50_000,
    max_html_chars_per_section: int = 120_000
) -> Dict[str, Any]:
    """
    Extrae “todo lo visible” de la pestaña por defecto de la página completa.
    
    Nota:
    - No renderizamos/ejecutamos nada; solo leemos DOM (texto/HTML).
    - Se trunca para evitar explosión de tamaño.
    """
    driver = get_driver()

    url = None
    title = None
    try:
        url = driver.current_url
    except Exception:
        pass
    try:
        title = driver.title
    except Exception:
        pass

    # Texto visible agregado (muy útil, pero puede ser grande).
    try:
        visible_text = driver.execute_script("return (document.body && document.body.innerText) ? document.body.innerText : '';")
    except Exception:
        visible_text = ""

    # Secciones HTML (heurísticas). No dependemos de una UI exacta.
    selectors = [
        "main",
        "#wrapper",
        "div.appContainerLibrayAndContentContainer",
        "div.appContainer",
        "div#root",
        "body",
    ]
    html_sections: list[Dict[str, Any]] = []
    for sel in selectors:
        try:
            html = driver.execute_script(
                "const el = document.querySelector(arguments[0]); return el ? el.outerHTML : null;",
                sel
            )
        except Exception:
            html = None
        if not html:
            continue
        html_sections.append({
            "selector": sel,
            "outer_html": _truncate_text(str(html), max_html_chars_per_section),
        })

    return {
        "current_url": url,
        "page_title": title,
        "visible_text": _truncate_text(str(visible_text), max_visible_text_chars),
        "html_sections": html_sections,
    }


def return_to_calendar_from_details(timeout: int = 12) -> None:
    """
    Retorna al calendario desde la página de detalle.
    
    Estrategia mínima y robusta:
    - driver.back()
    - esperar a que exista el contenedor de calendario (week containers) o el QuickView (si vuelve ahí).
    """
    driver = get_driver()
    try:
        driver.back()
    except Exception:
        return

    def _is_calendar_ready(d):
        try:
            if d.find_elements(By.CSS_SELECTOR, "div[data_cy='calendarWeekContainer']"):
                return True
        except Exception:
            pass
        try:
            if d.find_elements(By.ID, "quickViewContent"):
                return True
        except Exception:
            pass
        return False

    try:
        WebDriverWait(driver, timeout).until(_is_calendar_ready)
    except Exception:
        pass


def _simple_open_quickview_click(card, timeout=12):
    """
    Click simple sobre un target estable dentro de la card raíz del workout
    y espera a que aparezca #quickViewContent.
    """
    driver = get_driver()
    
    # Preferimos header; si no, fallback a .workoutDiv
    clickable = None
    for css in [
        ".activityHeader.newActivityUIHeader",
        ".workoutDiv"
    ]:
        try:
            el = card.find_element(By.CSS_SELECTOR, css)
            if el.is_displayed():
                clickable = el
                break
        except Exception:
            continue

    if clickable is None:
        raise RuntimeError("No encontré target clickeable dentro de la card.")

    # Scroll a vista y click simple
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", clickable)
    except Exception:
        pass

    clickable.click()

    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.ID, "quickViewContent"))
    )


def _simple_close_quickview(timeout=8):
    """Cerrar modal sin robust click: closeIcon -> overlay -> ESC + pequeño debounce."""
    driver = get_driver()
    
    # Si no hay modal, salir
    try:
        modal = WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".modalComponent .workoutQuickView"))
        )
    except Exception:
        return

    # 1) close icon
    try:
        modal.find_element(By.CSS_SELECTOR, "#closeIcon").click()
        WebDriverWait(driver, timeout).until(EC.invisibility_of_element(modal))
        time.sleep(0.05)   # micro-debounce para evitar re-disparos
        return
    except Exception:
        pass

    # 2) overlay
    try:
        driver.find_element(By.CSS_SELECTOR, ".modalComponent .modalOverlay.mask").click()
        WebDriverWait(driver, timeout).until(EC.invisibility_of_element(modal))
        time.sleep(0.05)
        return
    except Exception:
        pass

    # 3) ESC
    try:
        ActionChains(driver).send_keys(u"\ue00c").perform()  # ESC
        WebDriverWait(driver, timeout).until(EC.invisibility_of_element(modal))
        time.sleep(0.05)
    except Exception:
        pass


def get_calendar_quickview_data(timeout=20):
    """
    Extrae todos los datos relevantes del Quick View de un workout en el calendario:
      - Fecha / hora / recurrencia
      - Barra de workout (título, deporte, key stats, estado)
      - Summary (Planned / Completed)
      - Min / Avg / Max
      - Equipo
      - Descripción, adjuntos, comentarios, notas privadas
      - Estructura del workout (pasos)
      - Tabs disponibles / missingData

    Retorna:
        dict con toda la información, o None si no se encuentra el quickView.
    """
    driver = get_driver()
    
    def _safe(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _get_input_value_by_id(elem_id):
        el = _safe(lambda: driver.find_element(By.ID, elem_id))
        if not el:
            return None
        return _safe(lambda: el.get_attribute("value"), None)

    def _get_css_text(css, root=None):
        search_root = root if root is not None else driver
        el = _safe(lambda: search_root.find_element(By.CSS_SELECTOR, css))
        if not el:
            return None
        return _safe(lambda: el.text.strip(), None)

    # 1) Asegurar que el quickView esté presente
    try:
        qv_root = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "quickViewContent"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'start'});", qv_root)
    except Exception:
        print("No se encontró el contenedor #quickViewContent.")
        return None

    # -------------------------------------------------------------------------
    # 2) Fecha, hora y recurrencia (dateAndTime)
    # -------------------------------------------------------------------------
    date_time_container = _safe(lambda: driver.find_element(By.CSS_SELECTOR, ".dateAndTime"))
    date_time = {}
    if date_time_container:
        date_time = {
            "day_name": _get_css_text("#dayName", root=date_time_container),
            "calendar_date": _get_css_text("#calendarDate", root=date_time_container),
            "start_time": _safe(
                lambda: date_time_container.find_element(By.ID, "startTimeInput").get_attribute("value"),
                None
            ),
            "start_time_placeholder": _safe(
                lambda: date_time_container.find_element(By.ID, "startTimeInput").get_attribute("placeholder"),
                None
            ),
            "recurring_label": _get_css_text(".recurringBuilderLabel", root=date_time_container),
        }

    # -------------------------------------------------------------------------
    # 3) workoutBarView: título, deporte, key stats, estado
    # -------------------------------------------------------------------------
    workout_bar = {}
    wb = _safe(lambda: driver.find_element(By.CSS_SELECTOR, ".workoutBarView"))
    if wb:
        # estado (clases de la burbuja planned/notCompliant/isSkipped/past, etc.)
        compliance_div = _safe(
            lambda: wb.find_element(By.CSS_SELECTOR, ".workoutComplianceStatus")
        )
        compliance_classes = []
        if compliance_div:
            compliance_classes = (compliance_div.get_attribute("class") or "").split()

        # lock / hidden visibles
        lock_icon = _safe(lambda: wb.find_element(By.CSS_SELECTOR, ".lockIcon.statusIcon"))
        hidden_icon = _safe(lambda: wb.find_element(By.CSS_SELECTOR, ".hiddenIcon.statusIcon"))
        is_locked = bool(lock_icon and "hide" not in (lock_icon.get_attribute("class") or ""))
        is_hidden = bool(hidden_icon and "hide" not in (hidden_icon.get_attribute("class") or ""))

        # título
        title_input = _safe(lambda: wb.find_element(By.CSS_SELECTOR, "input.title.workoutTitle"))
        workout_title = _safe(lambda: title_input.get_attribute("value"), None) if title_input else None

        # deporte (Bike, Run, etc.)
        # Intento 1: h6 en el bloque de deporte
        sport = _get_css_text(".MuiStack-root h6", root=wb)
        # Intento 2: clase del div.workout (ej. "workout Bike")
        if not sport:
            sport_div = _safe(lambda: wb.find_element(By.CSS_SELECTOR, "div.workout"))
            if sport_div:
                classes = (sport_div.get_attribute("class") or "").split()
                # p.ej. ["workout", "Bike"]
                if len(classes) >= 2:
                    sport = classes[1]

        # key stats
        duration = _get_css_text(".keyStats .duration .value", root=wb)
        distance_val = _get_css_text(".keyStats .distance .value", root=wb)
        distance_units = _get_css_text(".keyStats .distance .units", root=wb)
        tss_val = _get_css_text(".keyStats .tss .value", root=wb)
        tss_units = _get_css_text(".keyStats .tss .units", root=wb)

        workout_bar = {
            "title": workout_title,
            "sport": sport,
            "status_classes": compliance_classes,
            "is_locked": is_locked,
            "is_hidden": is_hidden,
            "key_stats": {
                "duration": duration,
                "distance": {"value": distance_val, "units": distance_units},
                "tss": {"value": tss_val, "units": tss_units},
            },
        }

    # -------------------------------------------------------------------------
    # 4) Summary (Planned / Completed)
    # -------------------------------------------------------------------------
    planned_completed = {
        "duration": {
            "planned": _get_input_value_by_id("totalTimePlannedField"),
            "completed": _get_input_value_by_id("totalTimeCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .durationStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "distance": {
            "planned": _get_input_value_by_id("distancePlannedField"),
            "completed": _get_input_value_by_id("distanceCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .distanceStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "averageSpeed": {
            "planned": _get_input_value_by_id("averageSpeedPlannedField"),
            "completed": _get_input_value_by_id("averageSpeedCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .averageSpeedStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "calories": {
            "planned": _get_input_value_by_id("caloriesPlannedField"),
            "completed": _get_input_value_by_id("caloriesCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .caloriesStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "elevationGain": {
            "planned": _get_input_value_by_id("elevationGainPlannedField"),
            "completed": _get_input_value_by_id("elevationGainCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .elevationGainStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "tss": {
            "planned": _get_input_value_by_id("tssPlannedField"),
            "completed": _get_input_value_by_id("tssCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .TSSStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "if": {
            "planned": _get_input_value_by_id("ifPlannedField"),
            "completed": _get_input_value_by_id("ifCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .IFStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "normalizedPower": {
            "planned": _get_input_value_by_id("normalizedPowerPlanned"),
            "completed": _get_input_value_by_id("normalizedPowerCompleted"),
            "units": _get_css_text("#workoutPlannedCompletedStats .normalizedPowerStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "work_kJ": {
            "planned": _get_input_value_by_id("energyPlannedField"),
            "completed": _get_input_value_by_id("energyCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .energyStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "normalizedPace": {
            "planned": _get_input_value_by_id("normalizedPacePlannedField"),
            "completed": _get_input_value_by_id("normalizedPaceCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .normalizedPaceStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "averagePace": {
            "planned": _get_input_value_by_id("averagePacePlannedField"),
            "completed": _get_input_value_by_id("averagePaceCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .averagePaceStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "fatCalories": {
            "planned": _get_input_value_by_id("fatCaloriesPlannedField"),
            "completed": _get_input_value_by_id("fatCaloriesCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .fatCaloriesStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "carbCalories": {
            "planned": _get_input_value_by_id("carbCaloriesPlannedField"),
            "completed": _get_input_value_by_id("carbCaloriesCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .carbCaloriesStatsRow .workoutStatsUnitLabel label", qv_root)
        },
        "elevationLoss": {
            "planned": _get_input_value_by_id("elevationLossPlannedField"),
            "completed": _get_input_value_by_id("elevationLossCompletedField"),
            "units": _get_css_text("#workoutPlannedCompletedStats .elevationLossStatsRow .workoutStatsUnitLabel label", qv_root)
        },
    }

    # -------------------------------------------------------------------------
    # 5) Min / Avg / Max
    # -------------------------------------------------------------------------
    min_avg_max = {
        "heartRate": {
            "min": _get_input_value_by_id("hrMinField"),
            "avg": _get_input_value_by_id("hrAvgField"),
            "max": _get_input_value_by_id("hrMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .heartRateSummaryRow .workoutStatsUnitLabel label", qv_root)
        },
        "power": {
            "min": _get_input_value_by_id("powerMinField"),
            "avg": _get_input_value_by_id("powerAvgField"),
            "max": _get_input_value_by_id("powerMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .powerSummaryRow .workoutStatsUnitLabel label", qv_root)
        },
        "elevation": {
            "min": _get_input_value_by_id("elevationMinField"),
            "avg": _get_input_value_by_id("elevationAvgField"),
            "max": _get_input_value_by_id("elevationMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .elevationSummaryRow .workoutStatsUnitLabel label", qv_root)
        },
        "cadence": {
            "min": _get_input_value_by_id("cadenceMinField"),
            "avg": _get_input_value_by_id("cadenceAvgField"),
            "max": _get_input_value_by_id("cadenceMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .cadenceSummaryRow .workoutStatsUnitLabel label", qv_root)
        },
        "speed": {
            "min": _get_input_value_by_id("speedMinField"),
            "avg": _get_input_value_by_id("speedAvgField"),
            "max": _get_input_value_by_id("speedMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .speedSummaryRow .workoutStatsUnitLabel label", qv_root)
        },
        "pace": {
            "min": _get_input_value_by_id("paceMinField"),
            "avg": _get_input_value_by_id("paceAvgField"),
            "max": _get_input_value_by_id("paceMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .paceSummaryRow .workoutStatsUnitLabel label", qv_root)
        },
        "temperature": {
            "min": _get_input_value_by_id("tempMinField"),
            "avg": _get_input_value_by_id("tempAvgField"),
            "max": _get_input_value_by_id("tempMaxField"),
            "units": _get_css_text("#workoutMinMaxAvgStats .temperatureSummaryRow .workoutStatsUnitLabel label", qv_root)
        },
    }

    # -------------------------------------------------------------------------
    # 6) Equipment
    # -------------------------------------------------------------------------
    equipment = {}
    equip_root = _safe(lambda: driver.find_element(By.CSS_SELECTOR, ".equipment"))
    if equip_root:
        def _selected_option_text(sel_css):
            sel = _safe(lambda: equip_root.find_element(By.CSS_SELECTOR, sel_css))
            if not sel:
                return None
            opt = _safe(lambda: sel.find_element(By.CSS_SELECTOR, "option:checked"))
            return _safe(lambda: opt.text.strip(), None) if opt else None

        equipment = {
            "bike": _selected_option_text("select.bikeSelector"),
            "shoes": _selected_option_text("select.shoeSelector"),
            "pool_length": _selected_option_text("select.poolLengthSelector"),
        }

    # -------------------------------------------------------------------------
    # 7) Descripción, adjuntos, comentarios, notas privadas
    # -------------------------------------------------------------------------
    # Descripción
    description = _get_css_text("#descriptionPrintable", qv_root)
    if not description:
        desc_el = _safe(lambda: driver.find_element(By.CSS_SELECTOR, "#descriptionInput"))
        if desc_el:
            description = _safe(
                lambda: (desc_el.get_attribute("innerText") or desc_el.text or "").strip(),
                ""
            )

    # Adjuntos
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

    # Comentarios
    pre_activity = _get_css_text("#preActivityCommentsInput", qv_root)
    post_activity = _get_css_text("#postActivityCommentsInput", qv_root)

    # Notas privadas
    private_notes_text = None
    private_input = _safe(lambda: driver.find_element(By.ID, "privateNotesInput"))
    if private_input:
        # si solo hay placeholder, puede venir vacío o con el div.placeholder
        private_notes_text = _safe(
            lambda: (private_input.get_attribute("innerText") or private_input.text or "").strip(),
            ""
        )

    private_notes_count = _get_css_text("#privateNotesCharCount", qv_root)

    comments = {
        "description": description,
        "attachments": attachments,
        "pre_activity": pre_activity,
        "post_activity": post_activity,
        "private_notes": {
            "text": private_notes_text,
            "char_count": private_notes_count,
        },
    }

    # -------------------------------------------------------------------------
    # 8) Estructura del workout (texto)
    # -------------------------------------------------------------------------
    workout_details = {
        "header": _get_css_text(".workoutStructureTextHeader", qv_root),
        "steps": []
    }
    try:
        step_items = driver.find_elements(By.CSS_SELECTOR, ".workoutStructureText .stepList li")
        for li in step_items:
            txt = (li.text or "").strip()
            if txt:
                workout_details["steps"].append(txt)
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # 9) Tabs / estados (Summary, Map and Graph, etc.)
    # -------------------------------------------------------------------------
    tabs_info = []
    try:
        tabs = driver.find_elements(By.CSS_SELECTOR, "#quickViewContent .tabNavigation > div")
        for t in tabs:
            title = _safe(lambda: t.get_attribute("title"), None)
            classes = (t.get_attribute("class") or "").split()
            tabs_info.append({
                "title": title,
                "classes": classes,
                "is_selected": "tabSelected" in classes,
                "missingData": "missingData" in classes,
            })
    except Exception:
        pass

    result = {
        "date_time": date_time,
        "workout_bar": workout_bar,
        "planned_completed": planned_completed,
        "min_avg_max": min_avg_max,
        "equipment": equipment,
        "comments": comments,
        "workout_details": workout_details,
        "tabs": tabs_info,
    }

    print("Datos de Quick View del calendario extraídos ✅")
    return result


def get_all_quickviews_on_date(target_date, use_today=True, timeout=12, limit=None):
    """
    Abre el Quick View de CADA workout único en 'target_date' y devuelve
    una lista con los dicts que retorna get_calendar_quickview_data(),
    evitando aperturas duplicadas.
    - Sin robust click.
    - Desduplica por data-workoutid.
    - Cierra el modal entre extracciones con debounce.
    """
    driver = get_driver()
    
    # 1) Asegurar el día visible
    day_el = _ensure_day_visible(target_date, use_today=use_today)

    # 2) Localizar SOLO las cards raíz de workouts (1 por workout)
    #    Importante: pedimos el contenedor .activity.workout con data-workoutid
    cards = day_el.find_elements(
        By.CSS_SELECTOR,
        ".activities .activity.workout[data-workoutid]"
    )

    # 3) Desduplicar por workout_id y quedarnos con la primera card visible
    unique = {}
    for c in cards:
        try:
            if not c.is_displayed():
                continue
            wid = c.get_attribute("data-workoutid") or ""
            if wid and wid not in unique:
                unique[wid] = c
        except Exception:
            continue

    # 4) Armar la lista final de cards únicas (respetar limit)
    unique_cards = list(unique.values())
    if limit is not None:
        unique_cards = unique_cards[:limit]

    results = []
    for idx, card in enumerate(unique_cards, start=1):
        # (opcional) título esperado para validación rápida
        expected_title = None
        try:
            ttl = card.find_element(By.CSS_SELECTOR, "h6.newActivityUItitle")
            expected_title = (ttl.text or "").strip() or None
        except Exception:
            pass

        # 5) Abrir quickview (click simple sobre target estable)
        try:
            _simple_open_quickview_click(card, timeout=timeout)
        except Exception as e:
            print(f"[{idx}] no se pudo abrir quickview: {e}")
            continue

        # 6) (opcional) validar que el modal corresponde a la card (si hay título)
        if expected_title:
            try:
                WebDriverWait(driver, 5).until(
                    lambda d: (
                        d.find_element(By.CSS_SELECTOR, ".workoutBarView input.title.workoutTitle")
                         .get_attribute("value") or ""
                    ).strip() == expected_title
                )
            except Exception:
                # si no coincide, igual seguimos extrayendo; a veces TP renderiza con delay
                pass

        # 7) Extraer datos
        data = None
        try:
            data = get_calendar_quickview_data(timeout=timeout)
        except Exception as e:
            print(f"[{idx}] error extrayendo datos: {e}")

        # 7.1) Extraer detalle completo (página completa) desde Quick View (si es posible).
        # Importante: hacemos esto ANTES de cerrar el modal.
        try:
            if data is None:
                data = {}
            opened = open_full_workout_details_from_quickview(timeout=max(6, int(timeout)))
            if opened:
                # Esperar una señal mínima de carga de la página.
                try:
                    WebDriverWait(driver, max(6, int(timeout))).until(
                        lambda d: (d.execute_script("return document.readyState") or "") == "complete"
                    )
                except Exception:
                    pass
                data["full_details"] = extract_full_workout_page_visible_details()
                # Volver al calendario para continuar con el resto.
                return_to_calendar_from_details(timeout=max(8, int(timeout)))
        except Exception:
            # No bloquear extracción por fallas de detalle completo.
            pass

        # Enriquecer con metadatos
        try:
            wid = card.get_attribute("data-workoutid")
            if data is None:
                data = {}
            data.setdefault("_meta", {})
            data["_meta"].update({
                "index_in_day": idx,
                "workout_id": wid,
                "expected_title": expected_title
            })
        except Exception:
            pass

        if data is not None:
            results.append(data)

        # 8) Cerrar modal y micro-debounce
        _simple_close_quickview(timeout=timeout)

    return results


# =============== Ocultar workout del calendario ===============
def _find_calendar_workout_card(workout_title: str, target_date, timeout: int = 12):
    """
    Encuentra la card de un workout en el calendario por titulo y fecha.
    
    Args:
        workout_title: Titulo del workout a buscar
        target_date: Fecha donde buscar (YYYY-MM-DD | date | datetime)
        timeout: Tiempo maximo de espera
        
    Returns:
        Elemento de la card del workout
    """
    driver = get_driver()
    
    # Asegurar que el dia este visible
    day_el = _ensure_day_visible(target_date, use_today=False)
    
    # Buscar la card del workout por titulo
    title_key = (workout_title or "").strip()[:28]
    
    cards = day_el.find_elements(
        By.CSS_SELECTOR,
        ".activities .activity.workout[data-workoutid]"
    )
    
    for card in cards:
        try:
            if not card.is_displayed():
                continue
            # Buscar titulo dentro de la card
            title_els = card.find_elements(By.CSS_SELECTOR, "h6.newActivityUItitle, h6, .newActivityUItitle")
            for title_el in title_els:
                txt = (title_el.text or "").strip()
                if txt == workout_title or (title_key and title_key in txt):
                    return card
        except Exception:
            continue
    
    raise TimeoutException(f"No se encontro workout '{workout_title}' en fecha {target_date}")


def hide_calendar_workout(workout_title: str, target_date, timeout: int = 12) -> bool:
    """
    Oculta un workout del calendario usando el menu contextual (tomahawk).
    
    Pasos:
    1. Encuentra el workout en el calendario
    2. Click en tomahawk button (tres puntitos) dentro de la card
    3. Click en "Hide"
    
    Args:
        workout_title: Titulo del workout a ocultar
        target_date: Fecha del workout (YYYY-MM-DD | date | datetime)
        timeout: Tiempo maximo de espera para cada operacion
        
    Returns:
        True si se oculto exitosamente
    """
    driver = get_driver()
    
    # Paso 1: Encontrar la card del workout
    card = _find_calendar_workout_card(workout_title, target_date, timeout=timeout)
    
    # Hacer scroll para que la card sea visible
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
    time.sleep(0.2)
    
    # Paso 2: Click en tomahawk button (tres puntitos) DENTRO de la card
    # El boton tomahawk esta directamente en la card, no en un QuickView
    tomahawk_selectors = [
        "button[data_cy='tomahawkButton']",
        "button[data-cy='tomahawkButton']",
        ".contextMenuMUIIcon",
        "button.MuiIconButton-root",
    ]
    
    tomahawk_btn = None
    for sel in tomahawk_selectors:
        try:
            tomahawk_btn = card.find_element(By.CSS_SELECTOR, sel)
            if tomahawk_btn.is_displayed():
                break
            tomahawk_btn = None
        except Exception:
            continue
    
    if tomahawk_btn is None:
        raise TimeoutException("No se encontro el boton tomahawk en la card del workout")
    
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tomahawk_btn)
    try:
        tomahawk_btn.click()
    except Exception:
        driver.execute_script("arguments[0].click();", tomahawk_btn)
    
    # Paso 3: Click en "Hide"
    # Buscar el item del menu con texto "Hide"
    hide_selectors = [
        "//span[contains(@class,'MuiListItemText-primary') and normalize-space()='Hide']",
        "//li[contains(@class,'MuiMenuItem-root')]//span[normalize-space()='Hide']",
        "//span[normalize-space()='Hide']",
    ]
    
    hide_item = None
    for xp in hide_selectors:
        try:
            hide_item = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            break
        except Exception:
            continue
    
    if hide_item is None:
        raise TimeoutException("No se encontro la opcion 'Hide' en el menu")
    
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", hide_item)
    try:
        hide_item.click()
    except Exception:
        driver.execute_script("arguments[0].click();", hide_item)
    
    # Esperar breve para que se aplique el cambio
    time.sleep(0.3)
    
    return True
