"""
Workout Manager - Gestion unificada de operaciones sobre workouts

Este modulo proporciona una interfaz unificada para realizar operaciones
sobre workouts existentes en la Workout Library.
"""

from typing import Optional, Dict, Any
from .library_service import is_workout_library_open, is_library_expanded_by_name, workout_library
from .folder_service import click_workout_folder
from .creation_service import create_workout
from .workout_service import (
    click_workout,
    click_selected_workout_tomahawk_button,
    click_delete_workout_button,
    click_delete_workout_confirm_button,
    click_edit_workout_button,
    get_workout_modal_data,
    click_cancel_button
)


def manage_workout(library_name: str, workout_name: str, action: str) -> Optional[Dict[str, Any]]:
    """
    Realiza una accion especifica sobre un workout dentro de una Workout Library.
    
    Args:
        library_name: Nombre de la carpeta en la Workout Library.
        workout_name: Nombre del workout o titulo para crear.
        action: Accion a realizar:
            - "create" -> Crea un nuevo workout con el titulo especificado
            - "delete" -> Elimina un workout existente
            - "data"   -> Obtiene datos del workout (scraping del modal)
    
    Returns:
        Dict con datos del workout si action="data", None en otros casos.
    """
    # Asegurar que la Workout Library esta abierta y la carpeta expandida
    if is_workout_library_open():
        if is_library_expanded_by_name(library_name) == False:
            click_workout_folder(library_name)
    else:
        workout_library()
        if is_library_expanded_by_name(library_name) == False:
            click_workout_folder(library_name)

    # Ejecutar accion especifica
    if action == "create":
        # Crear un nuevo workout con el titulo dado
        result = create_workout(
            folder_name=library_name,
            title=workout_name,
            workout_type="Run",
            click_save=True
        )
        print(result)
        return None

    elif action == "delete":
        click_workout(workout_name)
        click_selected_workout_tomahawk_button()
        click_delete_workout_button()
        click_delete_workout_confirm_button()
        return None

    elif action == "data":
        click_workout(workout_name)
        click_selected_workout_tomahawk_button()
        click_edit_workout_button()
        data = get_workout_modal_data()
        click_cancel_button()
        return data

    else:
        print(f"Accion '{action}' no reconocida. Usa: 'create', 'delete' o 'data'.")
        return None
