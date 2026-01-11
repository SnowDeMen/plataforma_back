"""
Configuración del sync (mapeo Airtable -> Postgres).

La idea es que aquí tengas control total de:
- tabla origen Airtable
- tabla destino Postgres
- mapeos de campos
- transformaciones
- tipos (en SQL, vía DDL)

Este módulo no realiza I/O: solo define configuración.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .types import FieldMapping


@dataclass(frozen=True)
class TableSyncConfig:
    """
    Config de una tabla Airtable -> una tabla Postgres.

    NOTA sobre el PK:
    - Por defecto el PK en Postgres es airtable_record_id (estable).
    - Si existe un external_id en Airtable, puedes mapearlo a una columna
      y crear un UNIQUE INDEX para facilitar joins desde otros sistemas.
    """

    airtable_table_name: str
    airtable_last_modified_field: str
    target_schema: str
    target_table: str
    field_mappings: list[FieldMapping]
    external_id_column: Optional[str] = None
    record_id_column: str = "airtable_record_id"


def example_table_config_from_env() -> TableSyncConfig:
    """
    Config de ejemplo (sirve como plantilla).

    IMPORTANTE:
    - Ajusta los fields a los nombres reales de tu Airtable.
    - Alinea las columnas con tu DDL Postgres.
    """
    return TableSyncConfig(
        airtable_table_name="REEMPLAZA_POR_TU_TABLA",
        airtable_last_modified_field="Last Modified",
        target_schema="airtable",
        target_table="records_example",
        field_mappings=[
            FieldMapping(airtable_field="Nombre", pg_column="name", required=True),
            FieldMapping(airtable_field="Email", pg_column="email"),
            FieldMapping(airtable_field="Edad", pg_column="age", transform=lambda v: int(v) if v is not None else None),
            # Ejemplo de external_id si existe:
            # FieldMapping(airtable_field="external_id", pg_column="external_id"),
        ],
        external_id_column=None,
    )


