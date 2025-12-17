"""
Mapeos Airtable -> Postgres por tabla.

Este es el punto recomendado para que tengas “control total” sobre:
- qué columnas existen en Postgres
- cómo se transforman los valores de Airtable
- cómo se resuelven relaciones (FKs) cuando Airtable usa links

Patrón sugerido:
- Mantén el DDL en `schema.sql` alineado con estas definiciones.
- Define una función por tabla (o un diccionario) y selecciónala por AIRTABLE_TABLE_NAME.
"""

from __future__ import annotations

from .sync_config import TableSyncConfig
from .types import FieldMapping


def get_table_sync_config(
    *,
    airtable_table_name: str,
    airtable_last_modified_field: str,
    target_schema: str = "airtable",
    target_table: str | None = None,
) -> TableSyncConfig:
    """
    Retorna la configuración de sync para la tabla indicada.

    IMPORTANTE:
    - Edita este archivo para reflejar tu modelado real.
    - Si quieres modelado relacional, crea múltiples tablas y múltiples configs.
    """
    if not target_table:
        # Por defecto, usamos el nombre de tabla Airtable normalizado a snake_case simple.
        # Si tu tabla contiene espacios, se reemplazan por '_'.
        target_table = airtable_table_name.strip().lower().replace(" ", "_")

    # ---------------------------------------------------------------------
    # EJEMPLO: reemplaza esto por tu tabla real
    # ---------------------------------------------------------------------
    # Si NO quieres hardcodear por nombre, puedes simplemente devolver
    # un mapeo genérico para 1 tabla (tu caso actual).
    return TableSyncConfig(
        airtable_table_name=airtable_table_name,
        airtable_last_modified_field=airtable_last_modified_field,
        target_schema=target_schema,
        target_table=target_table,
        field_mappings=[
            # TODO: Cambia "Nombre", "Email", "Edad" por tus fields reales.
            FieldMapping(airtable_field="Nombre", pg_column="name", required=True),
            FieldMapping(airtable_field="Email", pg_column="email"),
            FieldMapping(
                airtable_field="Edad",
                pg_column="age",
                transform=lambda v: int(v) if v is not None else None,
            ),
        ],
        external_id_column=None,
    )


