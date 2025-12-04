"""
Módulo de Calendar - Gestión del calendario y navegación de fechas
"""

from .navigation_service import (
    week_forward,
    week_backward,
    calendar_go_to_today,
    _ensure_day_visible
)
from .date_service import (
    click_calendar_date_until,
    drag_workout_to_calendar
)
from .workout_service import (
    get_calendar_quickview_data,
    get_all_quickviews_on_date
)

__all__ = [
    # Navigation Service
    'week_forward',
    'week_backward',
    'calendar_go_to_today',
    '_ensure_day_visible',
    # Date Service
    'click_calendar_date_until',
    'drag_workout_to_calendar',
    # Workout Service
    'get_calendar_quickview_data',
    'get_all_quickviews_on_date'
]
