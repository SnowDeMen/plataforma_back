"""
Test manual para verificar la extraccion de RPE y "How did you feel?"
desde TrainingPeaks usando Selenium real.

Verifica que los selectores CSS del rpeContainer funcionan contra la UI
real de TrainingPeaks para workouts completados.

Ejecutar con:
    cd plataforma_back/api
    SELENIUM_HEADLESS=false python3 -m tests.manual.test_rpe_extraction

Argumentos opcionales:
    python3 -m tests.manual.test_rpe_extraction "Nombre Atleta" 7

Requiere:
    - .env con TP_EMAIL y TP_PASSWORD
    - chromedriver en PATH
    - Un atleta con al menos un workout completado en los ultimos N dias
"""
import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Agregar path para imports
api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))

tp_domain_path = api_path / "app" / "infrastructure" / "trainingpeaks"
sys.path.insert(0, str(tp_domain_path))

from app.infrastructure.driver.driver_manager import TRAININGPEAKS_URL
from app.infrastructure.driver.selenium_executor import run_selenium
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService


def _create_driver():
    """Crea un driver de Chrome configurado (visible)."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from app.core.config import settings

    opts = Options()
    if settings.SELENIUM_HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-infobars")

    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 10)
    driver.get(TRAININGPEAKS_URL)
    return driver, wait


def _format_rpe_data(data: dict) -> str:
    """Formatea los datos de perceived_exertion para impresion."""
    if not data:
        return "  (vacio — no se encontro datos RPE/feel)"
    lines = []
    feel = data.get("feel_value")
    feel_label = data.get("feel_label")
    if feel is not None:
        lines.append(f"  How did you feel?  : {feel}/5 ({feel_label or 'N/A'})")
    else:
        lines.append(f"  How did you feel?  : No encontrado")

    rpe = data.get("rpe_value")
    if rpe is not None:
        lines.append(f"  RPE                : {rpe}/10")
    else:
        lines.append(f"  RPE                : No encontrado")

    return "\n".join(lines)


async def test_rpe_extraction(athlete_name: str, days_back: int = 7):
    """
    Prueba la extraccion de RPE/feel de workouts completados.
    """
    print(f"\n{'='*70}")
    print(f"TEST: Extraccion de RPE / How did you feel?")
    print(f"Atleta: {athlete_name}")
    print(f"Dias a revisar: {days_back}")
    print(f"{'='*70}\n")

    driver = None
    found_rpe = False

    try:
        # 1. Crear driver
        print("[1/5] Creando driver...")
        driver, wait = await run_selenium(_create_driver)
        print("      OK\n")

        # 2. Login
        print("[2/5] Haciendo login en TrainingPeaks...")
        auth_service = AuthService(driver, wait)
        await run_selenium(auth_service.login_with_cookie)
        print("      OK\n")

        # 3. Seleccionar atleta
        print(f"[3/5] Seleccionando atleta '{athlete_name}'...")
        athlete_service = AthleteService(driver, wait)
        await run_selenium(athlete_service.select_athlete, athlete_name)
        print("      OK\n")

        # 4. Inyectar driver en tp_domain
        print("[4/5] Cargando funciones de dominio...")
        from tp_domain.core import set_driver
        from tp_domain.calendar.workout_service import get_all_quickviews_on_date
        set_driver(driver, wait)
        print("      OK\n")

        # 5. Recorrer dias buscando workouts con RPE
        print(f"[5/5] Buscando workouts completados con datos RPE...\n")

        today = date.today()
        total_workouts = 0
        workouts_with_rpe = 0

        for i in range(days_back):
            check_date = today - timedelta(days=i)
            iso = check_date.isoformat()

            print(f"  {iso} ... ", end="", flush=True)

            try:
                workouts = await run_selenium(
                    get_all_quickviews_on_date,
                    iso,
                    use_today=(i == 0),
                    timeout=12,
                    limit=None,
                )
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            if not workouts:
                print("sin workouts")
                continue

            print(f"{len(workouts)} workout(s)")

            for idx, w in enumerate(workouts):
                total_workouts += 1
                title = "?"
                try:
                    title = (w.get("workout_bar") or {}).get("title") or "Sin titulo"
                except Exception:
                    pass

                pe = w.get("perceived_exertion", {})
                has_data = bool(
                    pe and (pe.get("feel_value") is not None or pe.get("rpe_value") is not None)
                )

                if has_data:
                    workouts_with_rpe += 1
                    found_rpe = True

                marker = "** RPE ENCONTRADO **" if has_data else "(sin RPE)"
                print(f"    [{idx+1}] {title}  {marker}")

                if has_data:
                    print(_format_rpe_data(pe))
                    print()

        # Resumen
        print(f"\n{'='*70}")
        print("RESULTADO:")
        print(f"  Dias revisados          : {days_back}")
        print(f"  Total workouts          : {total_workouts}")
        print(f"  Workouts con RPE/feel   : {workouts_with_rpe}")
        print()

        if found_rpe:
            print("  EXITO: Los selectores CSS extraen RPE/feel correctamente.")
        else:
            print("  ADVERTENCIA: No se encontro ningun workout con datos RPE.")
            print("  Esto puede significar que:")
            print("    - Ningun workout completado tiene RPE registrado")
            print("    - Los selectores CSS no coinciden con la UI actual de TP")
            print("  Verifica manualmente que algun workout tenga 'How did you feel?'")

        return found_rpe

    except Exception as e:
        print(f"\nERROR durante el test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print()
        if driver:
            print("Cerrando driver...")
            try:
                driver.quit()
                print("Driver cerrado")
            except Exception as e:
                print(f"Error cerrando driver: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        athlete_name = sys.argv[1]
    else:
        athlete_name = input("Nombre del atleta (default: Luis Aragon): ").strip()
        if not athlete_name:
            athlete_name = "Luis Aragon"

    days = 7
    if len(sys.argv) > 2:
        days = int(sys.argv[2])

    result = asyncio.run(test_rpe_extraction(athlete_name, days))

    print(f"\n{'='*70}")
    print(f"TEST {'PASSED' if result else 'NEEDS VERIFICATION'}")
    print(f"{'='*70}")

    sys.exit(0 if result else 1)
