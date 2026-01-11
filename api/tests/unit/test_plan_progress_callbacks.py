from app.application.use_cases.plan_use_cases import PlanUseCases


def test_progress_callbacks_are_called() -> None:
    received: list[tuple[int, str]] = []

    def cb(progress: int, message: str) -> None:
        received.append((progress, message))

    plan_id = 123
    PlanUseCases.register_progress_callback(plan_id, cb)
    try:
        PlanUseCases._notify_progress(plan_id, 20, "Generando...")
        assert received == [(20, "Generando...")]
    finally:
        PlanUseCases.unregister_progress_callback(plan_id, cb)


def test_complete_callbacks_are_called() -> None:
    received: list[tuple[bool, str]] = []

    def cb(success: bool, message: str) -> None:
        received.append((success, message))

    plan_id = 456
    PlanUseCases.register_complete_callback(plan_id, cb)
    try:
        PlanUseCases._notify_complete(plan_id, True, "OK")
        assert received == [(True, "OK")]
    finally:
        PlanUseCases.unregister_complete_callback(plan_id, cb)


