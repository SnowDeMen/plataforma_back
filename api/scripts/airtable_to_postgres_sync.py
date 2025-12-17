"""
CLI: Airtable -> Postgres (one-way sync).

Uso recomendado:
  - Ejecutar como job (cron/systemd timer).
  - No se integra al request/response del API para evitar timeouts y bloquear workers.

Variables de entorno requeridas:
  - AIRTABLE_TOKEN
  - AIRTABLE_BASE_ID
  - AIRTABLE_TABLE_NAME
  - AIRTABLE_LAST_MOD_FIELD
  - DATABASE_URL (debe ser postgresql://... o postgres://...)

Ejecución:
  python scripts/airtable_to_postgres_sync.py
  python scripts/airtable_to_postgres_sync.py --schema-only
  python scripts/airtable_to_postgres_sync.py --reconcile-deletes
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from loguru import logger
from dotenv import load_dotenv

# Permite ejecutar este script desde cualquier cwd sin configurar PYTHONPATH.
# La carpeta "back/api" contiene el paquete raíz `app/`.
_BACK_API_ROOT = Path(__file__).resolve().parents[1]
if str(_BACK_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACK_API_ROOT))

# Cargar variables desde .env si existe.
# Soportamos dos ubicaciones típicas:
# - back/api/.env (recomendado para scripts del backend)
# - repo_root/.env (si centralizas variables del proyecto)
_REPO_ROOT = _BACK_API_ROOT.parent.parent
load_dotenv(_BACK_API_ROOT / ".env", override=False)
load_dotenv(_REPO_ROOT / ".env", override=False)

from app.infrastructure.external.airtable_sync.sync_service import build_from_env
from app.infrastructure.external.airtable_sync.table_mappings import get_table_sync_config


def _env_required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise SystemExit(f"Falta variable de entorno obligatoria: {name}")
    return val


def _stable_lock_key(namespace: str, table_name: str) -> int:
    """
    Genera un lock key reproducible para pg_advisory_lock.
    """
    # hash() no es estable entre procesos; implementamos algo determinista.
    # Sumatoria simple de bytes (suficiente para lock key, no para crypto).
    raw = (namespace + ":" + table_name).encode("utf-8")
    return int(sum(raw) % (2**31 - 1))


def _read_schema_sql() -> str:
    sql_path = Path(__file__).resolve().parents[1] / "app" / "infrastructure" / "external" / "airtable_sync" / "schema.sql"
    return sql_path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Solo imprime el DDL recomendado (no ejecuta sync).",
    )
    parser.add_argument(
        "--reconcile-deletes",
        action="store_true",
        help=(
            "Estrategia opcional: reconciliar deletes (full scan de IDs). "
            "Recomendado ejecutarlo 1 vez al día."
        ),
    )
    args = parser.parse_args()

    if args.schema_only:
        print(_read_schema_sql())
        return 0

    airtable_table = _env_required("AIRTABLE_TABLE_NAME")
    last_mod_field = _env_required("AIRTABLE_LAST_MOD_FIELD")

    # Construir servicio desde env (Airtable creds + DATABASE_URL)
    service, pg_repo, airtable = build_from_env(pg_dsn_env="DATABASE_URL")

    # Configurable y “editable por código”
    config = get_table_sync_config(
        airtable_table_name=airtable_table,
        airtable_last_modified_field=last_mod_field,
        target_schema=os.getenv("AIRTABLE_PG_SCHEMA", "airtable"),
        target_table=os.getenv("AIRTABLE_PG_TABLE") or None,
    )

    lock_key = _stable_lock_key("airtable_sync", config.airtable_table_name)

    logger.info("Iniciando Airtable -> Postgres sync...")
    result = service.run_once(config=config, pg_lock_key=lock_key)
    logger.info(f"Sync OK: upserted_rows={result.upserted_rows}, max_last_modified={result.max_last_modified}")

    # Reconciliación de deletes (opcional)
    if args.reconcile_deletes:
        logger.info("Reconciliación de deletes: iniciando full scan de IDs...")
        # Full scan de IDs (costo alto). Se implementa de forma simple:
        # - Trae todos los records con pageSize+offset, sin filtro
        # - Construye set de record_ids
        # - Marca faltantes como is_deleted=true en Postgres
        existing_ids: set[str] = set()
        url_table = config.airtable_table_name

        # Reutilizamos el cliente Airtable, pero sin incremental.
        # Para mantener el paquete pequeño, hacemos request manual aquí.
        # Si prefieres, se puede extraer a método iter_all_record_ids().
        base_url = "https://api.airtable.com/v0"
        url = f"{base_url}/{_env_required('AIRTABLE_BASE_ID')}/{url_table}"
        offset = None
        import requests

        headers = {"Authorization": f"Bearer {_env_required('AIRTABLE_TOKEN')}"}
        while True:
            params = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            for rec in payload.get("records", []) or []:
                rid = rec.get("id")
                if rid:
                    existing_ids.add(str(rid))
            offset = payload.get("offset")
            if not offset:
                break

        with pg_repo.connect() as conn:
            pg_repo.ensure_schema(conn, config.target_schema)
            deleted = pg_repo.soft_delete_missing_record_ids(
                conn,
                target_schema=config.target_schema,
                target_table=config.target_table,
                existing_record_ids=existing_ids,
            )
            conn.commit()
            logger.info(f"Reconciliación completada. Marcados como deleted: {deleted}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


