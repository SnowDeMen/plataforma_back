"""
Test manual que inyecta el HTML real del Quick View rpeContainer/feelContainer
en un Chrome local y ejecuta los MISMOS selectores que workout_service.py.

No requiere login a TrainingPeaks.

    cd plataforma_back/api
    python3 -m tests.manual.test_rpe_selectors
"""
import sys
from pathlib import Path

api_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(api_path))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


# HTML real del Quick View (tomado del DOM diagnosticado)
QV_HTML = """
<div id="quickViewContent">
  <!-- Other QV content ... -->
  <div class="rpeContainer MuiBox-root css-0">
    <svg width="18" height="18" viewBox="0 0 16 12" fill="none"
         xmlns="http://www.w3.org/2000/svg" class="rpeIcon">
      <path d="M7.19 8.28..." fill="#475569"></path>
    </svg>
    <p class="MuiTypography-root MuiTypography-body1 rpeText css-m3eua8-MuiTypography-root">2</p>
  </div>
  <div class="feelContainer MuiBox-root css-0">
    <p class="MuiTypography-root MuiTypography-body1 feelText css-m3eua8-MuiTypography-root">Very Strong</p>
  </div>
</div>
"""


def test_selectors():
    """Test Quick View RPE/feel selectors against real DOM."""
    print("\n" + "=" * 60)
    print("TEST: Quick View RPE/feel selectors")
    print("=" * 60 + "\n")

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=opts)

    try:
        driver.get("data:text/html;charset=utf-8,<html><body></body></html>")
        driver.execute_script("document.body.innerHTML = arguments[0];", QV_HTML)

        qv_root = driver.find_element(By.ID, "quickViewContent")

        # 1) .rpeText (RPE value 0-10)
        print("[1] Buscando .rpeText ...", end=" ")
        rpe_el = qv_root.find_element(By.CSS_SELECTOR, ".rpeText")
        rpe_text = rpe_el.text.strip()
        rpe_value = int(rpe_text)
        print(f"OK -> rpe_value = {rpe_value}/10")

        # 2) .feelText (feel label)
        print("[2] Buscando .feelText ...", end=" ")
        feel_el = qv_root.find_element(By.CSS_SELECTOR, ".feelText")
        feel_label = feel_el.text.strip()
        print(f'OK -> feel_label = "{feel_label}"')

        # 3) Map feel_label to numeric value
        FEEL_MAP = {
            "very weak": 1, "weak": 2, "normal": 3,
            "strong": 4, "very strong": 5,
        }
        feel_value = FEEL_MAP.get(feel_label.lower())
        print(f"[3] Mapped feel_value = {feel_value}/5")

        # Assertions
        print(f"\n{'='*60}")
        print("RESULTADO:")
        print(f"  rpe_value   : esperado=2   obtenido={rpe_value}")
        print(f"  feel_label  : esperado='Very Strong'  obtenido='{feel_label}'")
        print(f"  feel_value  : esperado=5   obtenido={feel_value}")
        print()

        assert rpe_value == 2
        assert feel_label == "Very Strong"
        assert feel_value == 5

        print("  TODOS LOS SELECTORES FUNCIONAN CORRECTAMENTE")
        return True

    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        driver.quit()


if __name__ == "__main__":
    result = test_selectors()
    print(f"\n{'='*60}")
    print(f"TEST {'PASSED' if result else 'FAILED'}")
    print(f"{'='*60}")
    sys.exit(0 if result else 1)
