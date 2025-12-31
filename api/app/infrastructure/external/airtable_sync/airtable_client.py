"""
Cliente mínimo de Airtable REST API (sin SDKs externos).

Requisitos cubiertos:
- requests
- paginación por offset
- rate-limit/backoff (429, 5xx)
- incremental fetch usando un campo "Last Modified Time"
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

import requests

from .types import AirtableRecord, ensure_utc


@dataclass(frozen=True)
class AirtableCredentials:
    token: str
    base_id: str


class AirtableApiError(RuntimeError):
    """Error de integración con Airtable."""


def _isoformat_z(dt: datetime) -> str:
    """
    Serializa datetime a ISO8601 con 'Z' (UTC) para fórmulas Airtable.
    """
    dt_utc = ensure_utc(dt)
    return dt_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_incremental_filter_formula(last_modified_field: str, cursor: datetime) -> str:
    """
    Construye una fórmula Airtable para traer registros incrementales:

    - Incluye igualdad (>=) para ser tolerante a cortes a mitad de página.
      La idempotencia queda asegurada por UPSERT en Postgres.

    Nota: Airtable no soporta operador >= directo en fórmulas con fechas.
    Se usa OR(IS_AFTER(...), IS_SAME(...)).
    """
    # DATETIME_PARSE es aceptado por Airtable para fechas ISO8601.
    # Usamos UTC (Z) para evitar ambigüedad.
    cursor_str = _isoformat_z(cursor)
    field_ref = "{" + last_modified_field + "}"
    return (
        f"OR("
        f"IS_AFTER({field_ref}, DATETIME_PARSE('{cursor_str}')), "
        f"IS_SAME({field_ref}, DATETIME_PARSE('{cursor_str}'))"
        f")"
    )


class AirtableClient:
    """
    Cliente HTTP de Airtable. Expone un generator que produce AirtableRecord.

    Importante:
    - No hace cast de tipos de campos: eso se decide en el mapeo de Postgres.
    - Sí asume que el campo last_modified_field viene en formato ISO8601.
    """

    def __init__(
        self,
        credentials: AirtableCredentials,
        *,
        session: Optional[requests.Session] = None,
        base_url: str = "https://api.airtable.com/v0",
        timeout_s: int = 30,
        max_retries: int = 6,
        min_backoff_s: float = 0.8,
        max_backoff_s: float = 20.0,
    ) -> None:
        self._creds = credentials
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._min_backoff_s = min_backoff_s
        self._max_backoff_s = max_backoff_s
        self._session = session or requests.Session()

    def iter_records_incremental(
        self,
        *,
        table_name: str,
        last_modified_field: str,
        cursor: datetime,
        fields: Optional[list[str]] = None,
        page_size: int = 100,
    ) -> Iterable[AirtableRecord]:
        """
        Itera registros de Airtable incrementalmente, ordenados por last_modified asc.

        - Usa filterByFormula para traer >= cursor
        - Maneja paginación por 'offset'
        """
        url = f"{self._base_url}/{self._creds.base_id}/{table_name}"
        offset: Optional[str] = None

        filter_formula = build_incremental_filter_formula(last_modified_field, cursor)
        sort = [{"field": last_modified_field, "direction": "asc"}]

        while True:
            params: dict[str, Any] = {
                "pageSize": page_size,
                "filterByFormula": filter_formula,
                # "sort": sort,  <-- REMOVE THIS to avoid bad serialization by requests
            }
            if offset:
                params["offset"] = offset
            if fields:
                # Airtable permite repetir "fields[]" en querystring.
                # requests lo serializa correctamente pasando lista de tuplas.
                pass

            # Construimos query para fields[] sin perder params principales.
            query: list[tuple[str, Any]] = list(params.items())
            
            # Manual serialization for 'sort' to avoid "sort=field&sort=direction"
            for i, s in enumerate(sort):
                query.append((f"sort[{i}][field]", s["field"]))
                query.append((f"sort[{i}][direction]", s["direction"]))

            if fields:
                for f in fields:
                    query.append(("fields[]", f))

            payload = self._request_json("GET", url, query=query)
            records = payload.get("records") or []

            for rec in records:
                rec_id = rec.get("id")
                rec_fields = rec.get("fields") or {}

                if not rec_id:
                    # Caso raro; preferimos fallar temprano y visible.
                    raise AirtableApiError("Airtable devolvió un record sin 'id'")

                raw_last_modified = rec_fields.get(last_modified_field)
                if not raw_last_modified:
                    raise AirtableApiError(
                        f"El record {rec_id} no contiene el campo '{last_modified_field}'. "
                        f"Configura AIRTABLE_LAST_MOD_FIELD correctamente o asegúrate que el field existe."
                    )

                try:
                    # Airtable devuelve string ISO8601, e.g. "2025-12-16T10:15:00.000Z"
                    dt = datetime.fromisoformat(
                        str(raw_last_modified).replace("Z", "+00:00")
                    )
                except Exception as e:
                    raise AirtableApiError(
                        f"No se pudo parsear '{last_modified_field}' del record {rec_id}: {raw_last_modified}"
                    ) from e

                yield AirtableRecord(
                    record_id=rec_id,
                    fields=rec_fields,
                    last_modified=ensure_utc(dt),
                )

            offset = payload.get("offset")
            if not offset:
                break

    def _request_json(
        self, method: str, url: str, *, query: list[tuple[str, Any]]
    ) -> dict[str, Any]:
        """
        Request HTTP con backoff para 429/5xx.

        Estrategia:
        - 429: respeta Retry-After si existe, si no exponencial con jitter simple.
        - 5xx: exponencial con jitter.
        - 4xx (no 429): error inmediato (config/auth mal).
        """
        headers = {
            "Authorization": f"Bearer {self._creds.token}",
            "Content-Type": "application/json",
        }

        for attempt in range(self._max_retries + 1):
            resp = self._session.request(
                method=method,
                url=url,
                params=query,
                headers=headers,
                timeout=self._timeout_s,
            )

            if 200 <= resp.status_code < 300:
                return resp.json()

            # Errores recuperables
            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                if attempt >= self._max_retries:
                    raise AirtableApiError(
                        f"Airtable error {resp.status_code} tras {attempt} reintentos: {resp.text}"
                    )

                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        sleep_s = float(retry_after)
                    except Exception:
                        sleep_s = self._min_backoff_s
                else:
                    # Exponencial simple + jitter proporcional
                    base = min(self._max_backoff_s, self._min_backoff_s * (2**attempt))
                    sleep_s = base + (0.15 * base)

                time.sleep(sleep_s)
                continue

            # Errores no recuperables
            raise AirtableApiError(
                f"Airtable request falló {resp.status_code}: {resp.text}"
            )


