-- ============================================================================
-- Airtable -> Postgres: DDL mínimo “production-ready”
--
-- Objetivos:
-- - Tabla de estado/cursor (sync_state) para incremental sync por tabla
-- - Tabla destino ejemplo con esquema explícito y tipado (sin JSON blobs)
-- - Campos técnicos: airtable_record_id (PK), airtable_last_modified, synced_at, is_deleted
--
-- NOTA:
-- - Ajusta el ejemplo de tabla a tu modelo real (y crea FKs/normalización).
-- - Puedes crear varias tablas destino y correr el pipeline por cada una.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS airtable;

-- 1) Estado del sync (cursor incremental por tabla)
CREATE TABLE IF NOT EXISTS sync_state (
    source               TEXT        NOT NULL,
    source_table         TEXT        NOT NULL,
    target_schema        TEXT        NOT NULL,
    target_table         TEXT        NOT NULL,

    cursor_last_modified TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01T00:00:00Z',

    last_run_started_at  TIMESTAMPTZ NULL,
    last_run_completed_at TIMESTAMPTZ NULL,
    last_run_status      TEXT NULL,  -- running | success | error
    last_run_error       TEXT NULL,

    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_table, target_schema, target_table)
);

-- 2) Tabla destino ejemplo (edítala según tu Airtable)
CREATE TABLE IF NOT EXISTS airtable.records_example (
    airtable_record_id      TEXT        PRIMARY KEY,
    airtable_last_modified  TIMESTAMPTZ NOT NULL,
    synced_at               TIMESTAMPTZ NOT NULL,
    is_deleted              BOOLEAN     NOT NULL DEFAULT FALSE,

    -- columnas de negocio (ejemplo)
    name                    TEXT        NOT NULL,
    email                   TEXT        NULL,
    age                     INTEGER     NULL
);

CREATE INDEX IF NOT EXISTS idx_records_example_last_modified
    ON airtable.records_example (airtable_last_modified);

CREATE INDEX IF NOT EXISTS idx_records_example_not_deleted
    ON airtable.records_example (is_deleted)
    WHERE is_deleted = FALSE;


