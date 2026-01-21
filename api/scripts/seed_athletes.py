"""
Script de migracion para cargar atletas desde JSON a PostgreSQL.

Uso:
    python -m scripts.seed_athletes              # Ejecutar migracion
    python -m scripts.seed_athletes --dry-run    # Ver que haria sin ejecutar
    python -m scripts.seed_athletes --force      # Actualizar atletas existentes
    python -m scripts.seed_athletes --file path  # Usar archivo JSON personalizado

Este script es idempotente y puede ejecutarse multiples veces.
En produccion, copiar el archivo data/athletes_seed.json al servidor
y ejecutar este script.

Nota: Campos desconocidos en el JSON (como 'personal', 'medica', 'deportiva')
son filtrados automaticamente para compatibilidad con diferentes estructuras.
"""
import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from loguru import logger


# Configurar path para imports
API_DIR = Path(__file__).parent.parent

# Campos validos del modelo AthleteModel
# Cualquier campo que no este en esta lista sera ignorado
ATHLETE_MODEL_FIELDS = {
    "id", "airtable_id", "created_at", "updated_at",
    "airtable_last_modified", "synced_at", "is_deleted",
    "name", "full_name", "last_name", "email", "tp_username", "tp_name", "status",
    "discipline", "level", "goal", "age", "experience",
    "consent", "date_of_birth", "gender", "country", "state", "city", "instagram",
    "emergency_contact_name", "emergency_contact_phone",
    "current_weight", "target_weight", "max_historical_weight", "height",
    "diseases_conditions", "acute_injury_disease", "acute_injury_type",
    "has_fractures_sprains_history", "fracture_history", "medications", "supplements",
    "smoker", "alcohol_consumption", "daily_sleep_hours", "sleep_quality",
    "meals_per_day", "diet_type", "diet_description",
    "athlete_type", "disciplines_count", "previous_sports",
    "running_experience_time", "cycling_experience_time", "swimming_experience_time",
    "short_term_goal", "medium_term_goal", "long_term_goal",
    "best_time_5k", "best_time_10k", "best_time_21k", "marathon_time",
    "triathlon_distance", "triathlon_time", "triathlon_place",
    "longest_run_distance", "longest_run_event", "longest_run_date",
    "training_frequency_weekly", "training_hours_weekly", "preferred_schedule", "schedule",
    "preferred_rest_day", "sacrifice_rest_day", "main_event", "event_type",
    "time_to_event", "secondary_events",
    "watch_brand_model", "has_watch", "watch_brand", "sensors_owned",
    "has_pool_access", "has_smart_trainer",
    "reason_for_sport", "annual_goals", "preferred_communication_channels",
    "whatsapp_group_interest", "discount", "client_status",
    "old_registration_date", "pending_payment", "form_link",
    "weight_objective_category", "bad_habits_percentage",
    "registration_date", "training_start_date",
    "performance"
}


def filter_athlete_data(athlete_data: dict) -> dict:
    """
    Filtra los datos del atleta para incluir solo campos validos del modelo.
    Esto permite que el script funcione con JSONs que tengan estructuras
    diferentes (campos anidados como 'personal', 'medica', 'deportiva').
    
    Args:
        athlete_data: Diccionario con datos del atleta (puede tener campos extras)
        
    Returns:
        Diccionario con solo los campos validos para AthleteModel
    """
    return {k: v for k, v in athlete_data.items() if k in ATHLETE_MODEL_FIELDS}
sys.path.insert(0, str(API_DIR))


async def load_athletes_data(file_path: Path) -> list:
    """
    Carga datos de atletas desde archivo JSON.
    
    Args:
        file_path: Ruta al archivo JSON
        
    Returns:
        Lista de diccionarios con datos de atletas
    """
    if not file_path.exists():
        logger.error(f"Archivo no encontrado: {file_path}")
        sys.exit(1)
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    logger.info(f"Cargados {len(data)} atletas desde {file_path}")
    return data


async def seed_athletes(
    athletes_data: list,
    dry_run: bool = False,
    force_update: bool = False
) -> dict:
    """
    Inserta o actualiza atletas en la base de datos.
    
    Args:
        athletes_data: Lista de diccionarios con datos de atletas
        dry_run: Si True, solo muestra que haria sin ejecutar
        force_update: Si True, actualiza atletas existentes
        
    Returns:
        Diccionario con estadisticas de la operacion
    """
    # Importar aqui para evitar problemas de imports circulares
    from app.infrastructure import database  # noqa: F401
    from app.infrastructure.database.session import AsyncSessionLocal, init_db
    from app.infrastructure.database.models import AthleteModel
    from sqlalchemy import select
    
    stats = {
        "total": len(athletes_data),
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0
    }
    
    if dry_run:
        logger.info("[DRY-RUN] Simulando migracion...")
    else:
        # Crear tablas si no existen
        logger.info("Inicializando base de datos...")
        await init_db()
    
    async with AsyncSessionLocal() as session:
        for athlete_data in athletes_data:
            athlete_id = athlete_data.get("id")
            athlete_name = athlete_data.get("name", "Sin nombre")
            
            if not athlete_id:
                logger.warning(f"Atleta sin ID: {athlete_name}")
                stats["errors"] += 1
                continue
            
            try:
                # Verificar si existe
                query = select(AthleteModel).where(AthleteModel.id == athlete_id)
                result = await session.execute(query)
                existing = result.scalar_one_or_none()
                
                # Filtrar datos para incluir solo campos validos del modelo
                filtered_data = filter_athlete_data(athlete_data)
                
                if existing:
                    if force_update:
                        if dry_run:
                            logger.info(f"[DRY-RUN] Actualizaria: {athlete_name} (ID: {athlete_id})")
                        else:
                            # Actualizar solo campos validos presentes en los datos
                            for field, value in filtered_data.items():
                                if field not in ("id", "created_at"):  # No sobrescribir estos
                                    setattr(existing, field, value)
                            existing.updated_at = datetime.utcnow()
                            logger.debug(f"Actualizado: {athlete_name}")
                        stats["updated"] += 1
                    else:
                        logger.debug(f"Saltando (ya existe): {athlete_name}")
                        stats["skipped"] += 1
                else:
                    if dry_run:
                        logger.info(f"[DRY-RUN] Insertaria: {athlete_name} (ID: {athlete_id})")
                    else:
                        # Crear nuevo atleta con datos filtrados
                        # Asegurar status por defecto
                        if "status" not in filtered_data:
                            filtered_data["status"] = "Por generar"
                        new_athlete = AthleteModel(**filtered_data)
                        session.add(new_athlete)
                        logger.debug(f"Insertado: {athlete_name}")
                    stats["inserted"] += 1
                    
            except Exception as e:
                logger.error(f"Error procesando atleta {athlete_name}: {e}")
                stats["errors"] += 1
        
        if not dry_run:
            await session.commit()
            logger.success("Cambios guardados en la base de datos")
    
    return stats


def print_stats(stats: dict, dry_run: bool = False):
    """Imprime estadisticas de la operacion."""
    prefix = "[DRY-RUN] " if dry_run else ""
    
    print("\n" + "=" * 50)
    print(f"{prefix}RESUMEN DE MIGRACION")
    print("=" * 50)
    print(f"Total atletas procesados: {stats['total']}")
    print(f"Insertados:               {stats['inserted']}")
    print(f"Actualizados:             {stats['updated']}")
    print(f"Saltados (ya existian):   {stats['skipped']}")
    print(f"Errores:                  {stats['errors']}")
    print("=" * 50 + "\n")


async def main():
    """Funcion principal del script."""
    parser = argparse.ArgumentParser(
        description="Migrar atletas desde JSON a PostgreSQL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular migracion sin hacer cambios"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Actualizar atletas que ya existen"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Ruta al archivo JSON (default: data/athletes_seed.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostrar mensajes de debug"
    )
    
    args = parser.parse_args()
    
    # Configurar logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    # Determinar archivo a usar
    if args.file:
        json_file = Path(args.file)
    else:
        json_file = API_DIR / "data" / "athletes_seed.json"
    
    logger.info(f"Archivo de origen: {json_file}")
    logger.info(f"Modo: {'DRY-RUN' if args.dry_run else 'EJECUTAR'}")
    logger.info(f"Forzar actualizacion: {'SI' if args.force else 'NO'}")
    
    # Cargar datos
    athletes_data = await load_athletes_data(json_file)
    
    # Ejecutar migracion
    stats = await seed_athletes(
        athletes_data,
        dry_run=args.dry_run,
        force_update=args.force
    )
    
    # Mostrar resultados
    print_stats(stats, args.dry_run)
    
    if stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

