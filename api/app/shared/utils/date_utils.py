from datetime import date, timedelta
from typing import Optional
from loguru import logger

def calculate_next_start_date(base_date: date, preferred_rest_day_str: Optional[str]) -> date:
    """
    Calcula la fecha de inicio bumping si cae en día de descanso.
    Maneja múltiples días continuos. Spanish-aware.
    """
    if not preferred_rest_day_str:
        return base_date
        
    # Mapeo de dias en español (comunmente vienen asi de Airtable/Form)
    dias_map = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6
    }
    
    # Limpiar y convertir a lista de ints
    rest_days = []
    parts = [p.strip().lower() for p in preferred_rest_day_str.replace(";", ",").split(",")]
    for p in parts:
        if p in dias_map:
            rest_days.append(dias_map[p])
    
    if not rest_days:
        return base_date
        
    current_date = base_date
    # Mientras el dia de la semana sea un dia de descanso, saltar al siguiente
    # weekday() es 0=Lunes, 6=Domingo
    # Limitamos a 7 bumps max para evitar bucles infinitos por config erronca (ej: poner todos los dias como descanso)
    attempts = 0
    while current_date.weekday() in rest_days and attempts < 7:
        logger.info(f"Bumping start_date {current_date} porque es dia de descanso ({preferred_rest_day_str})")
        current_date += timedelta(days=1)
        attempts += 1
        
    return current_date
