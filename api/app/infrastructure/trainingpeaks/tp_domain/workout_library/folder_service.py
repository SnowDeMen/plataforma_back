"""
Folder Service - Servicios de gestión de carpetas en Workout Library
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver import ActionChains
from ..core import get_driver, get_wait
from .library_service import is_library_expanded_by_name


def click_workout_folder(folder, exact=False):
    """
    Hace clic en una carpeta de Workout Library cuyo nombre coincide con `folder`.

    Parámetros:
        folder (str): nombre (o parte del nombre) de la carpeta.
        exact  (bool): 
            - True  -> match exacto (normalize-space() == folder o @data-tooltip == folder)
            - False -> match parcial (contains() sobre el texto o el data-tooltip)
    """
    driver = get_driver()
    wait = get_wait()
    
    # Predicado según exact / contains
    if exact:
        cond = "(normalize-space()='{t}' or @data-tooltip='{t}')".format(t=folder)
    else:
        cond = "(contains(normalize-space(), '{t}') or contains(@data-tooltip, '{t}'))".format(t=folder)

    # Raíz: sólo dentro del panel de libraries abierto y su contenedor de folders
    root_xpath = (
        "//div[@id='wrapper']//div[contains(@class,'appContainerLibrayAndContentContainer')]"
        "//div[contains(@class,'libraries') and contains(@class,'open')]"
        "//div[contains(@class,'workoutLibraryFoldersContainer') and contains(@class,'libraryContents')]"
    )

    # Localiza el titleContain de la carpeta
    title_xpath = (
        root_xpath +
        "//div[contains(@class,'titleContain') and {cond}]"
    ).format(cond=cond)

    title_el = wait.until(EC.presence_of_element_located((By.XPATH, title_xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", title_el)

    # Intento de hover inicial
    try:
        ActionChains(driver).move_to_element(title_el).perform()
    except Exception:
        pass

    # A partir del titleContain, buscamos ancestros potencialmente clicables
    candidates = [title_el]
    ancestor_relatives = [
        "ancestor::div[contains(@class,'groupTitle')][1]",
        "ancestor::div[contains(@class,'toggleArea')][1]",
        "ancestor::div[contains(@class,'listHeader')][1]",
    ]

    for rel in ancestor_relatives:
        try:
            anc = title_el.find_element(By.XPATH, rel)
            candidates.append(anc)
        except NoSuchElementException:
            continue

    last_err = None
    # Intentar click con todos los candidatos, de menor a mayor contenedor
    for el in candidates:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            try:
                wait.until(lambda d: el.is_displayed() and el.is_enabled())
            except Exception:
                pass

            # 1) click normal
            try:
                el.click()
                return
            except Exception as e1:
                last_err = e1

            # 2) Actions
            try:
                ActionChains(driver).move_to_element(el).pause(0.05).click().perform()
                return
            except Exception as e2:
                last_err = e2

            # 3) JS
            try:
                driver.execute_script("arguments[0].click();", el)
                return
            except Exception as e3:
                last_err = e3
                continue

        except Exception as e:
            last_err = e
            continue

    raise TimeoutException(f"No pude clickear la carpeta '{folder}'. Último error: {last_err}")


def folder_settings(folder):
    """
    Abre settings de una carpeta. Se le especifica el nombre de la carpeta en el parametro.
    """
    driver = get_driver()
    wait = get_wait()
    
    # Anclar el child del nombre de carpeta
    header_xpath = (
        "//div[contains(@class,'titleContain') and "
        "(normalize-space()='{t}' or @data-tooltip='{t}')]"
        "/ancestor::div[contains(@class,'listHeader')]"
    ).format(t=folder)

    header = wait.until(EC.presence_of_element_located((By.XPATH, header_xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", header)
    try:
        ActionChains(driver).move_to_element(header).perform()  # por si el icono aparece al hacer hover
    except Exception:
        pass

    # Click en boton de 3 puntitos
    btn_locator = (By.XPATH,
        header_xpath + "//div[@data_cy='folderSettingsButton' "
                       "or contains(@class,'foldersettingsButton') "
                       "or contains(@class,'folderSettingsButton') "
                       "or contains(@class,'folderSettingsButtonContainer')]"
    )

    btn = wait.until(EC.element_to_be_clickable(btn_locator))

    try:
        btn.click()
    except Exception:
        driver.execute_script("arguments[0].click();", btn)


def workout_folder(library_name, exact=True):
    """
    Abre la Workout Library con el nombre dado y asegura que esté expandida.
    
    Parámetros:
        library_name (str): nombre de la carpeta a buscar
        exact (bool): True para match exacto, False para match parcial
    """
    estado = is_library_expanded_by_name(library_name, exact)
    
    # Si retorna None, la carpeta no existe
    if estado is None:
        raise TimeoutException(f"No se encontró la carpeta '{library_name}' en Workout Library.")
    
    # Si retorna False, está cerrada -> hacer click
    if estado is False:
        click_workout_folder(library_name, exact)
        time.sleep(0.5)  # Pequeña pausa para que se expanda
    
    # Validar que la carpeta esté abierta después del click
    estado_final = is_library_expanded_by_name(library_name, exact)
    if estado_final is not True:
        raise TimeoutException(f"No se pudo abrir la carpeta '{library_name}' de Workout Library.")
    
    print(f"✅ Carpeta '{library_name}' lista para usar.")

