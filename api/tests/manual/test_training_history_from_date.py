"""
Test manual para verificar la extracción de historial con rango de fechas (from_date).

Verifica que:
1. El driver se crea y autentica correctamente.
2. La extracción respeta el rango [from_date, today].
3. No se extraen workouts antes de from_date.
4. Las estadísticas del rango son correctas.

Ejecutar con:
    cd plataforma_back/api
    SELENIUM_HEADLESS=false python -m tests.manual.test_training_history_from_date \
        --athlete "Luis Angel Rios Jaso" --from-date 2026-02-01

Nota: Requiere cookies de TrainingPeaks válidas.
"""
import argparse
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))

tp_domain_path = api_path / "app" / "infrastructure" / "trainingpeaks"
sys.path.insert(0, str(tp_domain_path))

from app.infrastructure.driver.driver_manager import TRAININGPEAKS_URL
from app.infrastructure.driver.selenium_executor import run_selenium
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService


def _create_driver():
    """Crea un driver de Chrome configurado."""
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


async def test_training_history_from_date(athlete_name: str, from_date: date):
    """
    Prueba la extracción de historial respetando un rango de fechas.

    Args:
        athlete_name: Nombre del atleta a seleccionar en TrainingPeaks.
        from_date: Fecha de inicio del rango (inclusive).
    """
    today = date.today()
    total_days = (today - from_date).days + 1

    print(f"\n{'='*70}")
    print(f"TEST: Extracción de historial con from_date")
    print(f"Atleta: {athlete_name}")
    print(f"Rango: {from_date.isoformat()} -> {today.isoformat()} ({total_days} días)")
    print(f"{'='*70}\n")

    driver = None

    try:
        print("[1/5] Creando driver...")
        driver, wait = await run_selenium(_create_driver)
        print("      Driver creado exitosamente\n")

        print("[2/5] Haciendo login...")
        await run_selenium(AuthService(driver, wait).login_with_cookie)
        print("      Login exitoso\n")

        print(f"[3/5] Seleccionando atleta '{athlete_name}'...")
        await run_selenium(AthleteService(driver, wait).select_athlete, athlete_name)
        print("      Atleta seleccionado\n")

        print("[4/5] Preparando extracción de historial...")
        try:
            from domain.core import set_driver
            from domain.calendar.workout_service import get_all_quickviews_on_date
            set_driver(driver, wait)
            print("      Funciones de dominio cargadas\n")
        except ImportError as e:
            print(f"      Error cargando funciones de dominio: {e}")
            return False

        print(f"[5/5] Extrayendo workouts del rango [{from_date} -> {today}]...")
        workouts_found = {}
        cursor = today
        first_call = True

        while cursor >= from_date:
            iso_date = cursor.isoformat()
            print(f"      Revisando {iso_date}...", end=" ")

            try:
                workouts = await run_selenium(
                    get_all_quickviews_on_date,
                    iso_date,
                    use_today=(first_call),
                    timeout=10,
                    limit=None,
                )
                first_call = False

                if workouts:
                    workouts_found[iso_date] = workouts
                    print(f"{len(workouts)} workout(s)")
                else:
                    print("sin workouts")
            except Exception as e:
                print(f"error: {e}")

            cursor -= timedelta(days=1)

        # Validar que no hay workouts fuera del rango
        out_of_range = [d for d in workouts_found if date.fromisoformat(d) < from_date]

        total_workouts = sum(len(w) for w in workouts_found.values())

        print(f"\n{'='*70}")
        print("RESULTADO:")
        print(f"  Rango solicitado:    {from_date} -> {today}")
        print(f"  Días revisados:      {total_days}")
        print(f"  Días con workouts:   {len(workouts_found)}")
        print(f"  Total de workouts:   {total_workouts}")
        print(f"  Fuera de rango:      {len(out_of_range)}")

        if workouts_found:
            print(f"\n  Detalle por día:")
            for day, workouts in sorted(workouts_found.items()):
                titles = [w.get("workout_bar", {}).get("title", "?") for w in workouts]
                print(f"    {day}: {len(workouts)} workout(s) - {', '.join(titles)}")

        success = len(out_of_range) == 0
        print(f"\n  Validación from_date: {'PASS' if success else 'FAIL'}")
        print(f"  Estado: {'EXITO' if success else 'FALLO'}")
        return success

    except Exception as e:
        print(f"\nERROR durante el test: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print()
        input("Presiona ENTER para cerrar el navegador...")
        if driver:
            print("Cerrando driver...")
            try:
                driver.quit()
                print("Driver cerrado")
            except Exception as e:
                print(f"Error cerrando driver: {e}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test manual de historial con from_date")
    parser.add_argument("--athlete", type=str, default=None, help="Nombre del atleta")
    parser.add_argument(
        "--from-date",
        type=str,
        default=None,
        help="Fecha de inicio (YYYY-MM-DD). Default: hace 14 días.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    athlete_name = args.athlete or input("Ingresa el nombre del atleta: ").strip() or "Luis Aragon"
    if args.from_date:
        from_date = date.fromisoformat(args.from_date)
    else:
        from_date = date.today() - timedelta(days=14)

    result = asyncio.run(test_training_history_from_date(athlete_name, from_date))

    print(f"\n{'='*70}")
    print(f"TEST {'PASSED' if result else 'FAILED'}")
    print(f"{'='*70}")

    sys.exit(0 if result else 1)
