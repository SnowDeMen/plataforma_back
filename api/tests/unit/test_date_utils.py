from datetime import date
from app.shared.utils.date_utils import calculate_next_start_date

def test_calculate_next_start_date_no_rest_days():
    # Base date: Wednesday, Oct 4, 2023
    base_date = date(2023, 10, 4)
    result = calculate_next_start_date(base_date, None)
    assert result == base_date

    result2 = calculate_next_start_date(base_date, "")
    assert result2 == base_date

def test_calculate_next_start_date_single_rest_day():
    # Base date: Monday, Oct 2, 2023 (weekday 0)
    base_date = date(2023, 10, 2)
    # Lunes is rest day, should bump to Tuesday
    result = calculate_next_start_date(base_date, "lunes")
    assert result == date(2023, 10, 3)

def test_calculate_next_start_date_multiple_rest_days():
    # Base date: Saturday, Oct 7, 2023 (weekday 5)
    base_date = date(2023, 10, 7)
    # Rest days: Saturday and Sunday
    result = calculate_next_start_date(base_date, "sábado, domingo")
    # Should bump to Monday, Oct 9
    assert result == date(2023, 10, 9)

def test_calculate_next_start_date_with_semicolon():
    # Base date: Tuesday, Oct 3, 2023 (weekday 1)
    base_date = date(2023, 10, 3)
    # Rest days separated by semicolon
    result = calculate_next_start_date(base_date, "martes;miércoles")
    # Should bump to Thursday, Oct 5
    assert result == date(2023, 10, 5)

def test_calculate_next_start_date_max_bumps():
    # Base date: Monday, Oct 2, 2023
    base_date = date(2023, 10, 2)
    # Rest days: every day of the week
    rest_days = "lunes, martes, miércoles, jueves, viernes, sábado, domingo"
    result = calculate_next_start_date(base_date, rest_days)
    # The while loop breaks after 7 bumps to avoid infinite loop
    # 7 bumps from Monday Oct 2 means it lands on Monday Oct 9
    assert result == date(2023, 10, 9)

def test_calculate_next_start_date_no_bump_needed():
    # Base date: Wednesday, Oct 4, 2023 (weekday 2)
    base_date = date(2023, 10, 4)
    # Rest day: lunes
    result = calculate_next_start_date(base_date, "lunes")
    # Should stay the same
    assert result == base_date
