from app.application.use_cases.training_history_policy import (
    should_stop_after_gap,
    sort_day_keys_ascending,
)


def test_should_not_stop_before_finding_any_workout() -> None:
    assert should_stop_after_gap(
        has_found_any_workout=False,
        consecutive_empty_days=999,
        gap_days=180,
    ) is False


def test_should_stop_after_gap_once_found_workout() -> None:
    assert should_stop_after_gap(
        has_found_any_workout=True,
        consecutive_empty_days=179,
        gap_days=180,
    ) is False

    assert should_stop_after_gap(
        has_found_any_workout=True,
        consecutive_empty_days=180,
        gap_days=180,
    ) is True


def test_sort_day_keys_ascending_orders_iso_dates() -> None:
    keys = ["2026-01-11", "2025-12-01", "2026-01-01"]
    assert sort_day_keys_ascending(keys) == ["2025-12-01", "2026-01-01", "2026-01-11"]


