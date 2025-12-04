"""
Modulo de Workout Library - Gestion de entrenamientos y carpetas

Incluye servicios para:
- Abrir y verificar el panel de Workout Library
- Gestionar carpetas de entrenamientos
- Crear entrenamientos directamente en la plataforma
- Listar y manipular workouts existentes
"""

from .library_service import (
    workout_library,
    is_workout_library_open,
    is_library_expanded_by_name,
    click_workout_library
)
from .folder_service import (
    folder_settings,
    workout_folder,
    click_workout_folder
)
from .creation_service import (
    # Funciones de creacion de workout
    click_create_workout,
    set_workout_title,
    click_add_button,
    click_workout_type_option,
    set_workout_description,
    set_pre_activity_comments,
    click_save_button,
    get_workout_modal_input_parameters,
    create_workout
)
from .workout_service import (
    click_workout,
    click_selected_workout_tomahawk_button,
    click_edit_workout_button,
    click_delete_workout_button,
    click_delete_workout_confirm_button,
    get_workout_modal_data,
    list_workouts_in_library,
    click_cancel_button
)
from .workout_manager import manage_workout

__all__ = [
    # Library Service
    'workout_library',
    'is_workout_library_open',
    'is_library_expanded_by_name',
    'click_workout_library',
    # Folder Service
    'folder_settings',
    'workout_folder',
    'click_workout_folder',
    # Creation Service
    'click_create_workout',
    'set_workout_title',
    'click_add_button',
    'click_workout_type_option',
    'set_workout_description',
    'set_pre_activity_comments',
    'click_save_button',
    'get_workout_modal_input_parameters',
    'create_workout',
    # Workout Service
    'click_workout',
    'click_selected_workout_tomahawk_button',
    'click_edit_workout_button',
    'click_delete_workout_button',
    'click_delete_workout_confirm_button',
    'get_workout_modal_data',
    'list_workouts_in_library',
    'click_cancel_button',
    # Workout Manager
    'manage_workout'
]
