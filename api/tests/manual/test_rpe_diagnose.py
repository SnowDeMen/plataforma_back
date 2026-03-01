"""
Diagnostic v3: Uses get_all_quickviews_on_date (production code path)
and dumps the perceived_exertion + full DOM around rpeContainer.

    cd plataforma_back/api
    SELENIUM_HEADLESS=false python3 -m tests.manual.test_rpe_diagnose "Lilly" 3
"""
import asyncio
import sys
import time
from datetime import date, timedelta
from pathlib import Path

api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))
tp_domain_path = api_path / "app" / "infrastructure" / "trainingpeaks"
sys.path.insert(0, str(tp_domain_path))

from selenium.webdriver.common.by import By
from app.infrastructure.driver.driver_manager import TRAININGPEAKS_URL
from app.infrastructure.driver.selenium_executor import run_selenium
from app.infrastructure.driver.services.auth_service import AuthService
from app.infrastructure.driver.services.athlete_service import AthleteService


def _create_driver():
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


def _dump_rpe_from_dom(driver):
    """Search for ALL rpe/emoji/feel related elements in entire page."""
    results = driver.execute_script("""
        var all = document.querySelectorAll('*');
        var found = [];
        for (var i = 0; i < all.length; i++) {
            var cls = (all[i].className || '').toString().toLowerCase();
            var text = (all[i].textContent || '').trim();
            if (cls.indexOf('rpe') !== -1 || cls.indexOf('emoji') !== -1 || cls.indexOf('feel') !== -1) {
                found.push({
                    tag: all[i].tagName,
                    cls: (all[i].className || '').toString().substring(0, 150),
                    text: text.substring(0, 80),
                    html: all[i].outerHTML.substring(0, 400),
                    children: all[i].children.length
                });
            }
        }
        return found;
    """)
    return results


async def main(athlete_name, days_back):
    print(f"\n{'='*70}")
    print(f"RPE DOM Dump for '{athlete_name}'")
    print(f"{'='*70}\n")

    driver = None
    try:
        driver, wait = await run_selenium(_create_driver)
        print("[1] Driver OK")
        await run_selenium(AuthService(driver, wait).login_with_cookie)
        print("[2] Login OK")
        await run_selenium(AthleteService(driver, wait).select_athlete, athlete_name)
        print(f"[3] Athlete OK\n")

        from tp_domain.core import set_driver
        from tp_domain.calendar.workout_service import get_all_quickviews_on_date
        set_driver(driver, wait)

        today = date.today()
        for i in range(days_back):
            d = today - timedelta(days=i)
            iso = d.isoformat()
            print(f"--- {iso} ---")

            try:
                workouts = await run_selenium(
                    get_all_quickviews_on_date, iso,
                    use_today=(i == 0), timeout=12, limit=None
                )
            except Exception as e:
                print(f"  ERROR: {e}\n")
                continue

            if not workouts:
                print("  No workouts\n")
                continue

            for idx, w in enumerate(workouts):
                title = (w.get("workout_bar") or {}).get("title", "?")
                pe = w.get("perceived_exertion", {})
                print(f"  [{idx+1}] {title}")
                print(f"      perceived_exertion = {pe}")

                # After extraction, also dump the DOM to see what's there
                rpe_els = await run_selenium(_dump_rpe_from_dom, driver)
                if rpe_els:
                    print(f"      DOM elements with rpe/emoji/feel ({len(rpe_els)}):")
                    for el in rpe_els:
                        if el['children'] < 3:  # only leaf/near-leaf elements
                            print(f"        <{el['tag']}> cls=\"{el['cls'][:80]}\" text=\"{el['text'][:50]}\"")
                print()

            # Only check first day with workouts
            break

        return True
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "Lilly"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    asyncio.run(main(name, days))
