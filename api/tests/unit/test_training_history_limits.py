from app.application.use_cases.training_history_limits import enforce_workout_limits


def test_enforce_workout_limits_truncates_visible_text() -> None:
    workout = {
        "workout_bar": {"title": "Test"},
        "full_details": {
            "visible_text": "A" * 100,
            "html_sections": [],
        },
    }

    limited, changed = enforce_workout_limits(
        workout,
        max_visible_text_chars=10,
        max_workout_bytes=10_000,
    )

    assert changed is True
    assert isinstance(limited["full_details"]["visible_text"], str)
    assert len(limited["full_details"]["visible_text"]) <= 10 + len("…(truncado)")


def test_enforce_workout_limits_limits_html_sections_and_truncates_html() -> None:
    workout = {
        "full_details": {
            "visible_text": "ok",
            "html_sections": [
                {"selector": "a", "outer_html": "X" * 50},
                {"selector": "b", "outer_html": "Y" * 50},
                {"selector": "c", "outer_html": "Z" * 50},
            ],
        }
    }

    limited, changed = enforce_workout_limits(
        workout,
        max_html_sections=2,
        max_html_chars_per_section=10,
        max_workout_bytes=10_000,
    )

    assert changed is True
    hs = limited["full_details"]["html_sections"]
    assert isinstance(hs, list)
    assert len(hs) == 2
    assert len(hs[0]["outer_html"]) <= 10 + len("…(truncado)")


