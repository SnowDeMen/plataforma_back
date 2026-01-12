"""
Políticas puras para extracción de historial.

Este módulo NO toca Selenium, DB ni FastAPI.
Sirve para testear el criterio de corte y reglas de ordenamiento.
"""

from __future__ import annotations


def should_stop_after_gap(
    *,
    has_found_any_workout: bool,
    consecutive_empty_days: int,
    gap_days: int
) -> bool:
    """
    Determina si debe detenerse la búsqueda hacia atrás.

    Reglas:
    - Antes de encontrar algún entreno, nunca se corta por gap (para evitar cortar en 0).
    - Una vez encontrado al menos 1 entreno, se corta cuando el gap alcanza `gap_days`.
    """
    if gap_days <= 0:
        # Seguridad: en práctica el DTO lo valida, pero mantenemos contrato explícito.
        return False
    if not has_found_any_workout:
        return False
    return consecutive_empty_days >= gap_days


def sort_day_keys_ascending(day_keys: list[str]) -> list[str]:
    """
    Ordena claves YYYY-MM-DD ascendente.
    """
    return sorted(day_keys)


