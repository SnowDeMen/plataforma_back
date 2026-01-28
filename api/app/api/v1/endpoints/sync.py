"""
Endpoints para sincronizacion de datos externos.
Permite sincronizar Airtable con PostgreSQL desde la UI.
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel


router = APIRouter(prefix="/sync", tags=["Sync"])


class SyncResultDTO(BaseModel):
    """Resultado de la sincronizacion."""
    success: bool
    upserted_rows: int
    message: str
    max_last_modified: str | None = None
    full_sync: bool = False


def _reset_sync_cursor(pg_repo, config) -> None:
    """
    Resetea el cursor de sincronizacion a epoch (1970-01-01).
    Esto fuerza un full sync en la proxima ejecucion.
    """
    with pg_repo.connect() as conn:
        pg_repo.ensure_sync_state_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sync_state
                SET cursor_last_modified = %s,
                    updated_at = now()
                WHERE source = %s
                  AND source_table = %s
                  AND target_schema = %s
                  AND target_table = %s
                """,
                (
                    datetime(1970, 1, 1, tzinfo=timezone.utc),
                    "airtable",
                    config.airtable_table_name,
                    config.target_schema,
                    config.target_table,
                ),
            )
        conn.commit()
    logger.info(f"Cursor reseteado para full sync: {config.airtable_table_name}")


def _run_airtable_sync(full_sync: bool = False) -> Dict[str, Any]:
    """
    Ejecuta la sincronizacion de Airtable a PostgreSQL.
    Esta funcion es sincrona y se ejecuta en un thread separado.
    
    Args:
        full_sync: Si True, resetea el cursor para sincronizar todos los registros
    
    Returns:
        Dict con el resultado de la sincronizacion
    """
    from app.infrastructure.external.airtable_sync.sync_service import build_from_env
    from app.infrastructure.external.airtable_sync.table_mappings import get_table_sync_config
    
    # Leer configuracion desde variables de entorno
    airtable_table = os.getenv("AIRTABLE_TABLE_NAME", "Formulario_Inicial")
    last_mod_field = os.getenv("AIRTABLE_LAST_MOD_FIELD", "Last Modified")
    target_schema = os.getenv("AIRTABLE_PG_SCHEMA", "public")
    target_table = os.getenv("AIRTABLE_PG_TABLE") or None
    
    # Construir servicio desde variables de entorno
    service, pg_repo, _ = build_from_env(pg_dsn_env="DATABASE_URL")
    
    # Obtener configuracion de mapeo para la tabla
    config = get_table_sync_config(
        airtable_table_name=airtable_table,
        airtable_last_modified_field=last_mod_field,
        target_schema=target_schema,
        target_table=target_table,
    )
    
    # Si es full sync, resetear el cursor primero
    if full_sync:
        _reset_sync_cursor(pg_repo, config)
    
    # Generar lock key estable
    raw = (f"airtable_sync:{config.airtable_table_name}").encode("utf-8")
    lock_key = int(sum(raw) % (2**31 - 1))
    
    # Ejecutar sincronizacion
    result = service.run_once(config=config, pg_lock_key=lock_key)
    
    return {
        "upserted_rows": result.upserted_rows,
        "max_last_modified": result.max_last_modified.isoformat() if result.max_last_modified else None,
        "full_sync": full_sync,
    }


@router.post(
    "/airtable",
    response_model=SyncResultDTO,
    status_code=status.HTTP_200_OK,
    summary="Sincronizar Airtable con PostgreSQL"
)
async def sync_airtable(
    full_sync: bool = Query(
        default=True,
        description="Si True, sincroniza todos los registros. Si False, solo los modificados recientemente."
    )
) -> SyncResultDTO:
    """
    Ejecuta la sincronizacion de Airtable a PostgreSQL.
    
    La sincronizacion:
    - Si full_sync=True: Resetea el cursor y sincroniza todos los registros
    - Si full_sync=False: Solo sincroniza registros modificados desde el ultimo sync
    - Usa un lock para evitar ejecuciones concurrentes
    
    Returns:
        SyncResultDTO con el numero de registros sincronizados
    """
    try:
        sync_type = "completa (full sync)" if full_sync else "incremental"
        logger.info(f"Iniciando sincronizacion {sync_type} Airtable -> PostgreSQL desde API")
        
        # Ejecutar sync en thread separado para no bloquear el event loop
        result = await asyncio.to_thread(_run_airtable_sync, full_sync)
        
        rows = result["upserted_rows"]
        message = (
            f"Sincronizacion {sync_type} completada: {rows} registro(s) actualizado(s)"
            if rows > 0
            else "Sin cambios en Airtable"
        )
        
        logger.info(f"Sync completado: {message}")
        
        return SyncResultDTO(
            success=True,
            upserted_rows=rows,
            message=message,
            max_last_modified=result.get("max_last_modified"),
            full_sync=result.get("full_sync", False),
        )
        
    except Exception as e:
        logger.error(f"Error en sincronizacion Airtable: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar: {str(e)}"
        )
