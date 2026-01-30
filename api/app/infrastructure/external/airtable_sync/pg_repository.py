"""
Repositorio Postgres (psycopg) para:
- tabla objetivo (UPSERT)
- tabla de cursor/estado de sync
- reconciliación de borrados (opcional)

Se usa psycopg (v3) para cumplir el requisito del pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

import psycopg
from psycopg.rows import dict_row

from .types import ensure_utc, utc_now


class SyncStateError(RuntimeError):
    """Error relacionado con el estado/cursor del sync."""


@dataclass(frozen=True)
class SyncState:
    """
    Estado persistido por tabla (cursor incremental).

    cursor_last_modified:
        marca el "punto" de lectura en Airtable (>= cursor).
        Se guarda como timestamptz.
    """

    source: str
    source_table: str
    target_schema: str
    target_table: str
    cursor_last_modified: datetime
    updated_at: datetime


class PostgresSyncRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def connect(self) -> psycopg.Connection:
        """
        Abre conexión (autocommit False). El caller controla commits.
        """
        try:
            return psycopg.connect(self._dsn, row_factory=dict_row)
        except psycopg.OperationalError as e:
            # Error común en dev: usar hostname de Docker (resuelve solo dentro de la red de Docker).
            raise psycopg.OperationalError(
                f"{e}\n"
                f"Sugerencia: verifica que DATABASE_URL sea accesible desde donde ejecutas el script.\n"
                f"- Si DATABASE_URL apunta a un hostname de Docker (p.ej. 'postgres' o '...-1'), eso solo resuelve dentro de Docker.\n"
                f"- Desde Windows host, usa un hostname/IP real o 'localhost' con el puerto mapeado (5432) y asegúrate que Postgres esté corriendo."
            ) from e

    def try_advisory_lock(self, conn: psycopg.Connection, lock_key: int) -> bool:
        """
        Evita ejecuciones simultáneas del mismo job.
        """
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s) AS locked", (lock_key,))
            row = cur.fetchone()
            return bool(row and row.get("locked"))

    def ensure_sync_state_table(self, conn: psycopg.Connection) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    source              TEXT        NOT NULL,
                    source_table        TEXT        NOT NULL,
                    target_schema       TEXT        NOT NULL,
                    target_table        TEXT        NOT NULL,
                    cursor_last_modified TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01T00:00:00Z',
                    last_run_started_at TIMESTAMPTZ NULL,
                    last_run_completed_at TIMESTAMPTZ NULL,
                    last_run_status     TEXT NULL,
                    last_run_error      TEXT NULL,
                    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (source, source_table, target_schema, target_table)
                );
                """
            )

    def load_or_init_state(
        self,
        conn: psycopg.Connection,
        *,
        source: str,
        source_table: str,
        target_schema: str,
        target_table: str,
    ) -> SyncState:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source, source_table, target_schema, target_table,
                       cursor_last_modified, updated_at
                FROM sync_state
                WHERE source = %s
                  AND source_table = %s
                  AND target_schema = %s
                  AND target_table = %s
                """,
                (source, source_table, target_schema, target_table),
            )
            row = cur.fetchone()

            if row:
                return SyncState(
                    source=row["source"],
                    source_table=row["source_table"],
                    target_schema=row["target_schema"],
                    target_table=row["target_table"],
                    cursor_last_modified=ensure_utc(row["cursor_last_modified"]),
                    updated_at=ensure_utc(row["updated_at"]),
                )

            # Inicialización explícita con cursor epoch
            cur.execute(
                """
                INSERT INTO sync_state (source, source_table, target_schema, target_table)
                VALUES (%s, %s, %s, %s)
                """,
                (source, source_table, target_schema, target_table),
            )
            cur.execute(
                """
                SELECT source, source_table, target_schema, target_table,
                       cursor_last_modified, updated_at
                FROM sync_state
                WHERE source = %s
                  AND source_table = %s
                  AND target_schema = %s
                  AND target_table = %s
                """,
                (source, source_table, target_schema, target_table),
            )
            row2 = cur.fetchone()
            if not row2:
                raise SyncStateError("No se pudo inicializar sync_state")

            return SyncState(
                source=row2["source"],
                source_table=row2["source_table"],
                target_schema=row2["target_schema"],
                target_table=row2["target_table"],
                cursor_last_modified=ensure_utc(row2["cursor_last_modified"]),
                updated_at=ensure_utc(row2["updated_at"]),
            )

    def mark_run_started(
        self,
        conn: psycopg.Connection,
        *,
        state: SyncState,
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sync_state
                SET last_run_started_at = now(),
                    last_run_status = 'running',
                    last_run_error = NULL,
                    updated_at = now()
                WHERE source = %s
                  AND source_table = %s
                  AND target_schema = %s
                  AND target_table = %s
                """,
                (state.source, state.source_table, state.target_schema, state.target_table),
            )

    def mark_run_finished(
        self,
        conn: psycopg.Connection,
        *,
        state: SyncState,
        status: str,
        error: Optional[str],
    ) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sync_state
                SET last_run_completed_at = now(),
                    last_run_status = %s,
                    last_run_error = %s,
                    updated_at = now()
                WHERE source = %s
                  AND source_table = %s
                  AND target_schema = %s
                  AND target_table = %s
                """,
                (
                    status,
                    error,
                    state.source,
                    state.source_table,
                    state.target_schema,
                    state.target_table,
                ),
            )

    def advance_cursor(
        self,
        conn: psycopg.Connection,
        *,
        state: SyncState,
        new_cursor_last_modified: datetime,
    ) -> None:
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
                    ensure_utc(new_cursor_last_modified),
                    state.source,
                    state.source_table,
                    state.target_schema,
                    state.target_table,
                ),
            )

    def ensure_schema(self, conn: psycopg.Connection, schema: str) -> None:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}";')

    def upsert_rows(
        self,
        conn: psycopg.Connection,
        *,
        target_schema: str,
        target_table: str,
        rows: Iterable[dict[str, Any]],
        conflict_pk: str = "airtable_record_id",
        last_modified_col: str = "airtable_last_modified",
        soft_delete_col: str = "is_deleted",
    ) -> int:
        """
        UPSERT por PK (airtable_record_id). Resuelve conflictos con regla:
        - solo actualiza si excluded.airtable_last_modified >= target.airtable_last_modified

        Esto evita pisar con data vieja en ejecuciones concurrentes/reintentos.
        """
        rows_list = list(rows)
        if not rows_list:
            return 0

        # Columnas: asumimos que todas las filas traen el mismo conjunto.
        columns = list(rows_list[0].keys())
        if conflict_pk not in columns:
            raise ValueError(f"Falta PK '{conflict_pk}' en row para UPSERT")
        if last_modified_col not in columns:
            raise ValueError(f"Falta columna '{last_modified_col}' en row para UPSERT")

        quoted_cols = [f'"{c}"' for c in columns]
        placeholders = ", ".join(["%s"] * len(columns))
        insert_cols_sql = ", ".join(quoted_cols)

        # SET para UPDATE: no actualizamos PK.
        update_cols = [c for c in columns if c != conflict_pk]
        set_sql = ", ".join([f'"{c}" = EXCLUDED."{c}"' for c in update_cols])

        # Además: si el registro se vuelve a ver en Airtable, lo "revivimos" (is_deleted=false).
        # Esto se logra si soft_delete_col viene en la fila (recomendado).
        sql = f"""
            INSERT INTO "{target_schema}"."{target_table}" ({insert_cols_sql})
            VALUES ({placeholders})
            ON CONFLICT ("{conflict_pk}")
            DO UPDATE SET
                {set_sql}
            WHERE EXCLUDED."{last_modified_col}" >= "{target_schema}"."{target_table}"."{last_modified_col}"
            RETURNING "{conflict_pk}", (xmax = 0) AS is_insert;
        """

        values = [tuple(row[c] for c in columns) for row in rows_list]
        inserted_ids = []

        with conn.cursor() as cur:
            for val in values:
                cur.execute(sql, val)
                row = cur.fetchone()
                if row and row.get("is_insert"):
                    inserted_ids.append(str(row[conflict_pk]))
            
            return inserted_ids

    def soft_delete_missing_record_ids(
        self,
        conn: psycopg.Connection,
        *,
        target_schema: str,
        target_table: str,
        existing_record_ids: set[str],
        pk_col: str = "airtable_record_id",
        soft_delete_col: str = "is_deleted",
    ) -> int:
        """
        Reconciliación (full scan) de deletes:
        marca como is_deleted=true aquellos PK que existen en Postgres pero ya no están en Airtable.

        Nota: esto requiere haber obtenido el set completo de record_ids de Airtable (caro).
        Se recomienda ejecutarlo 1 vez al día (o menos).
        """
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT "{pk_col}" FROM "{target_schema}"."{target_table}" WHERE "{soft_delete_col}" = false'
            )
            pg_ids = {str(r[pk_col]) for r in cur.fetchall()}

        missing = pg_ids - existing_record_ids
        if not missing:
            return 0

        now = utc_now()
        missing_list = list(missing)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE "{target_schema}"."{target_table}"
                SET "{soft_delete_col}" = true,
                    synced_at = %s
                WHERE "{pk_col}" = ANY(%s)
                """,
                (now, missing_list),
            )
            return cur.rowcount or 0


