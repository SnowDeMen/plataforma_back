"""
Pipeline de sincronización one-way: Airtable -> PostgreSQL.

Este paquete está diseñado para ejecutarse como job (cron / task scheduler),
no como parte del request/response del API.

Objetivos de diseño:
- Idempotencia: se puede ejecutar N veces sin duplicar datos.
- Incremental: se apoya en un campo "Last Modified Time" en Airtable.
- Esquema explícito y tipado en PostgreSQL (sin blobs JSON).
- Control total: mapeo/transformaciones/resolución de conflictos en código.
"""


