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
                
                if existing:
                    if force_update:
                        if dry_run:
                            logger.info(f"[DRY-RUN] Actualizaria: {athlete_name} (ID: {athlete_id})")
                        else:
                            # Actualizar campos
                            existing.name = athlete_data.get("name", existing.name)
                            existing.age = athlete_data.get("age", existing.age)
                            existing.discipline = athlete_data.get("discipline", existing.discipline)
                            existing.level = athlete_data.get("level", existing.level)
                            existing.goal = athlete_data.get("goal", existing.goal)
                            existing.status = athlete_data.get("status", existing.status)
                            existing.experience = athlete_data.get("experience", existing.experience)
                            existing.personal = athlete_data.get("personal", existing.personal)
                            existing.medica = athlete_data.get("medica", existing.medica)
                            existing.deportiva = athlete_data.get("deportiva", existing.deportiva)
                            existing.performance = athlete_data.get("performance", existing.performance)
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
                        # Crear nuevo atleta
                        new_athlete = AthleteModel(
                            id=athlete_id,
                            name=athlete_data.get("name"),
                            age=athlete_data.get("age"),
                            discipline=athlete_data.get("discipline"),
                            level=athlete_data.get("level"),
                            goal=athlete_data.get("goal"),
                            status=athlete_data.get("status", "Por generar"),
                            experience=athlete_data.get("experience"),
                            personal=athlete_data.get("personal"),
                            medica=athlete_data.get("medica"),
                            deportiva=athlete_data.get("deportiva"),
                            performance=athlete_data.get("performance")
                        )
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

