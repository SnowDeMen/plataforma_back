from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("psycopg")

from app.infrastructure.external.airtable_sync.pg_repository import PostgresSyncRepository


class _DummyCursor:
    def __init__(self) -> None:
        self.executed_sql: str | None = None
        self.executemany_values = None
        self.rowcount = 1

    def executemany(self, sql: str, values) -> None:
        self.executed_sql = sql
        self.executemany_values = values

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyConn:
    def __init__(self) -> None:
        self._cursor = _DummyCursor()

    def cursor(self):
        return self._cursor


def test_upsert_generates_on_conflict_and_last_modified_guard() -> None:
    repo = PostgresSyncRepository("postgresql://dummy")
    conn = _DummyConn()
    now = datetime(2025, 12, 16, 10, 15, 0, tzinfo=timezone.utc)
    rows = [
        {
            "airtable_record_id": "rec123",
            "airtable_last_modified": now,
            "synced_at": now,
            "is_deleted": False,
            "name": "Ana",
        }
    ]
    count = repo.upsert_rows(conn, target_schema="airtable", target_table="records_example", rows=rows)
    assert count == 1
    sql = conn._cursor.executed_sql or ""
    assert "ON CONFLICT" in sql
    assert "WHERE EXCLUDED.\"airtable_last_modified\" >= \"airtable\".\"records_example\".\"airtable_last_modified\"" in sql


