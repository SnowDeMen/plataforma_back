from __future__ import annotations

from datetime import datetime, timezone

from app.infrastructure.external.airtable_sync.airtable_client import (
    build_incremental_filter_formula,
)


def test_build_incremental_filter_formula_includes_same_and_after() -> None:
    cursor = datetime(2025, 12, 16, 10, 15, 0, tzinfo=timezone.utc)
    formula = build_incremental_filter_formula("Last Modified", cursor)
    assert "IS_AFTER" in formula
    assert "IS_SAME" in formula
    assert "{Last Modified}" in formula
    assert "2025-12-16T10:15:00Z" in formula


