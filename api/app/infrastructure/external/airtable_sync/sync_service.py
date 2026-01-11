"""
Servicio de sincronización Airtable -> Postgres.

Diseño (resumen):
- Carga cursor (last_modified) desde Postgres (tabla sync_state)
- Consulta Airtable incrementalmente (>= cursor)
- Mapea fields a columnas tipadas (sin JSON blobs)
- UPSERT por airtable_record_id
- Avanza cursor al máximo last_modified visto en esta corrida

Estrategia de idempotencia:
- UPSERT con condición de "last_modified más nuevo" para evitar overwrites con data vieja.
- Filtro Airtable usa >= cursor, por lo que puede re-leer el borde (seguro).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from loguru import logger

from .airtable_client import AirtableClient, AirtableCredentials
from .pg_repository import PostgresSyncRepository
from .sync_config import TableSyncConfig
from .types import AirtableRecord, ensure_utc, utc_now


class SyncConfigError(RuntimeError):
    """Error de configuración del pipeline."""


def _env_required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise SyncConfigError(f"Falta variable de entorno obligatoria: {name}")
    return val


def _default_cursor_epoch() -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def map_airtable_record_to_row(
    record: AirtableRecord,
    *,
    config: TableSyncConfig,
    synced_at: datetime,
) -> dict[str, Any]:
    """
    Mapea un AirtableRecord a un dict listo para UPSERT.

    Reglas:
    - Se guardan columnas técnicas: airtable_record_id, airtable_last_modified, synced_at, is_deleted
    - Cada FieldMapping decide cómo mapear y transformar el valor
    """
    row: dict[str, Any] = {
        config.record_id_column: record.record_id,
        "airtable_last_modified": ensure_utc(record.last_modified),
        "synced_at": ensure_utc(synced_at),
        "is_deleted": False,  # si el registro existe en Airtable, no está borrado
    }

    for m in config.field_mappings:
        if m.airtable_field not in record.fields:
            if m.required:
                raise SyncConfigError(
                    f"Record {record.record_id} no contiene field requerido '{m.airtable_field}'"
                )
            row[m.pg_column] = None
            continue

        raw = record.fields.get(m.airtable_field)
        row[m.pg_column] = m.transform(raw) if m.transform else raw

    return row


@dataclass(frozen=True)
class SyncResult:
    upserted_rows: int
    max_last_modified: Optional[datetime]


class AirtableToPostgresSync:
    """
    Orquestador del pipeline para una tabla.
    """

    def __init__(
        self,
        *,
        pg_repo: PostgresSyncRepository,
        airtable: AirtableClient,
        source_name: str = "airtable",
        upsert_batch_size: int = 200,
    ) -> None:
        self._pg = pg_repo
        self._airtable = airtable
        self._source_name = source_name
        self._upsert_batch_size = upsert_batch_size

    def run_once(
        self,
        *,
        config: TableSyncConfig,
        pg_lock_key: int,
        fields_whitelist: Optional[list[str]] = None,
    ) -> SyncResult:
        """
        Ejecuta una corrida incremental completa para la tabla configurada.
        """
        with self._pg.connect() as conn:
            self._pg.ensure_schema(conn, config.target_schema)
            self._pg.ensure_sync_state_table(conn)

            if not self._pg.try_advisory_lock(conn, pg_lock_key):
                logger.warning("Sync ya está corriendo (advisory lock ocupado). Saliendo.")
                return SyncResult(upserted_rows=0, max_last_modified=None)

            state = self._pg.load_or_init_state(
                conn,
                source=self._source_name,
                source_table=config.airtable_table_name,
                target_schema=config.target_schema,
                target_table=config.target_table,
            )
            self._pg.mark_run_started(conn, state=state)

            try:
                result = self._run_incremental(conn, config=config, state_cursor=state.cursor_last_modified, fields_whitelist=fields_whitelist)
                if result.max_last_modified:
                    self._pg.advance_cursor(conn, state=state, new_cursor_last_modified=result.max_last_modified)
                self._pg.mark_run_finished(conn, state=state, status="success", error=None)
                conn.commit()
                return result
            except Exception as e:
                conn.rollback()
                # Intentar persistir el error del run. Si esto falla, igual relanzamos.
                try:
                    self._pg.mark_run_finished(conn, state=state, status="error", error=str(e)[:2000])
                    conn.commit()
                except Exception:
                    conn.rollback()
                raise

    def _run_incremental(
        self,
        conn,
        *,
        config: TableSyncConfig,
        state_cursor: datetime,
        fields_whitelist: Optional[list[str]],
    ) -> SyncResult:
        cursor = state_cursor or _default_cursor_epoch()
        logger.info(
            f"Sync incremental: Airtable '{config.airtable_table_name}' -> "
            f'Postgres "{config.target_schema}"."{config.target_table}" '
            f"(cursor >= {cursor.isoformat()})"
        )

        synced_at = utc_now()
        max_last_modified: Optional[datetime] = None
        total_upserted = 0

        # Si el caller no pasó whitelist, pedimos:
        # - last_modified_field (siempre)
        # - todos los campos mapeados
        if fields_whitelist is None:
            fields_whitelist = [config.airtable_last_modified_field] + [
                m.airtable_field for m in config.field_mappings
            ]

        batch: list[dict[str, Any]] = []
        for record in self._airtable.iter_records_incremental(
            table_name=config.airtable_table_name,
            last_modified_field=config.airtable_last_modified_field,
            cursor=cursor,
            fields=fields_whitelist,
        ):
            row = map_airtable_record_to_row(record, config=config, synced_at=synced_at)
            batch.append(row)
            max_last_modified = (
                record.last_modified if max_last_modified is None else max(max_last_modified, record.last_modified)
            )

            if len(batch) >= self._upsert_batch_size:
                total_upserted += self._pg.upsert_rows(
                    conn,
                    target_schema=config.target_schema,
                    target_table=config.target_table,
                    rows=batch,
                    conflict_pk=config.record_id_column,
                )
                batch.clear()

        if batch:
            total_upserted += self._pg.upsert_rows(
                conn,
                target_schema=config.target_schema,
                target_table=config.target_table,
                rows=batch,
                conflict_pk=config.record_id_column,
            )
            batch.clear()

        logger.info(f"Sync completado. upserts={total_upserted}, max_last_modified={max_last_modified}")
        return SyncResult(upserted_rows=total_upserted, max_last_modified=max_last_modified)


def build_from_env(
    *,
    pg_dsn_env: str = "DATABASE_URL",
) -> tuple[AirtableToPostgresSync, PostgresSyncRepository, AirtableClient]:
    """
    Constructor “oficial” del pipeline leyendo variables de entorno.

    Env vars Airtable requeridas:
    - AIRTABLE_TOKEN
    - AIRTABLE_BASE_ID
    """
    token = _env_required("AIRTABLE_TOKEN")
    base_id = _env_required("AIRTABLE_BASE_ID")

    pg_dsn_raw = _env_required(pg_dsn_env)
    pg_dsn = _normalize_psycopg_dsn(pg_dsn_raw)
    if "postgres" not in pg_dsn:
        # Requisito: destino es Postgres. Evitamos errores silenciosos en SQLite.
        raise SyncConfigError(
            f"{pg_dsn_env} debe apuntar a Postgres. Valor actual: {pg_dsn_raw}"
        )

    airtable = AirtableClient(AirtableCredentials(token=token, base_id=base_id))
    pg_repo = PostgresSyncRepository(pg_dsn)
    service = AirtableToPostgresSync(pg_repo=pg_repo, airtable=airtable)
    return service, pg_repo, airtable


def _normalize_psycopg_dsn(dsn: str) -> str:
    """
    Normaliza DSNs que vienen en formato SQLAlchemy async hacia un DSN aceptado por psycopg.

    Ejemplos:
    - postgresql+asyncpg://user:pass@host:5432/db  -> postgresql://user:pass@host:5432/db
    - postgres+asyncpg://...                      -> postgres://...

    Si el DSN ya es compatible, se retorna tal cual.
    """
    # psycopg acepta: postgresql://... o postgres://... o conninfo "key=value".
    if "://" not in dsn:
        return dsn

    scheme, rest = dsn.split("://", 1)
    if "+asyncpg" in scheme:
        scheme = scheme.replace("+asyncpg", "")
    if "+psycopg" in scheme:
        scheme = scheme.replace("+psycopg", "")
    return f"{scheme}://{rest}"


