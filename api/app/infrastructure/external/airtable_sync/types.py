"""
Tipos y utilidades puras para el pipeline Airtable -> Postgres.

Se mantienen libres de I/O para poder testearlos fácilmente.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")


def utc_now() -> datetime:
    """Retorna la hora actual en UTC, como datetime aware."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """
    Normaliza datetime a UTC (aware).

    Airtable suele devolver ISO8601 con zona; aun así, normalizamos para
    comparar/almacenar de forma consistente.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class AirtableRecord:
    """Registro Airtable mínimo para sync."""

    record_id: str
    fields: dict[str, Any]
    last_modified: datetime


Transform = Callable[[Any], Any]


@dataclass(frozen=True)
class FieldMapping:
    """
    Define el mapeo de un campo Airtable a una columna Postgres.

    - airtable_field: nombre del field en Airtable
    - pg_column: nombre de la columna en Postgres
    - transform: función opcional para transformar el valor antes de persistir
    - required: si True, el valor debe existir (si falta se levanta error)
    """

    airtable_field: str
    pg_column: str
    transform: Optional[Transform] = None
    required: bool = False


