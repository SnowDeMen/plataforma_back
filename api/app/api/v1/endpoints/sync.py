"""
Endpoints para sincronizacion de datos externos.
Permite sincronizar Airtable con PostgreSQL desde la UI.
"""
import asyncio
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from loguru import logger
from pydantic import BaseModel


router = APIRouter(prefix="/sync", tags=["Sync"])


class SyncResultDTO(BaseModel):
    """Resultado de la sincronizacion."""
    success: bool
    upserted_rows: int
    message: str
    max_last_modified: str | None = None


def _run_airtable_sync() -> Dict[str, Any]:
    """
    Ejecuta la sincronizacion de Airtable a PostgreSQL.
    Esta funcion es sincrona y se ejecuta en un thread separado.
    
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
    
    # Generar lock key estable
    raw = (f"airtable_sync:{config.airtable_table_name}").encode("utf-8")
    lock_key = int(sum(raw) % (2**31 - 1))
    
    # Ejecutar sincronizacion
    result = service.run_once(config=config, pg_lock_key=lock_key)
    
    return {
        "upserted_rows": result.upserted_rows,
        "max_last_modified": result.max_last_modified.isoformat() if result.max_last_modified else None,
    }


@router.post(
    "/airtable",
    response_model=SyncResultDTO,
    status_code=status.HTTP_200_OK,
    summary="Sincronizar Airtable con PostgreSQL"
)
async def sync_airtable() -> SyncResultDTO:
    """
    Ejecuta la sincronizacion incremental de Airtable a PostgreSQL.
    
    La sincronizacion:
    - Lee registros modificados desde el ultimo sync
    - Actualiza o inserta registros en PostgreSQL
    - Usa un lock para evitar ejecuciones concurrentes
    
    Returns:
        SyncResultDTO con el numero de registros sincronizados
    """
    try:
        logger.info("Iniciando sincronizacion Airtable -> PostgreSQL desde API")
        
        # Ejecutar sync en thread separado para no bloquear el event loop
        result = await asyncio.to_thread(_run_airtable_sync)
        
        rows = result["upserted_rows"]
        message = (
            f"Sincronizacion completada: {rows} registro(s) actualizado(s)"
            if rows > 0
            else "Sin cambios nuevos en Airtable"
        )
        
        logger.info(f"Sync completado: {message}")
        
        return SyncResultDTO(
            success=True,
            upserted_rows=rows,
            message=message,
            max_last_modified=result.get("max_last_modified"),
        )
        
    except Exception as e:
        logger.error(f"Error en sincronizacion Airtable: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar: {str(e)}"
        )
