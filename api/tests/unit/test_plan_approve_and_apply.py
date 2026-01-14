import pytest

from app.application.dto.plan_dto import PlanApplyRequestDTO, PlanWorkoutDTO
from app.application.use_cases.plan_use_cases import PlanUseCases
from app.application.interfaces.trainingpeaks_plan_publisher import PlanPublishResult
from app.infrastructure.repositories.plan_repository import PlanRepository


class _FakePublisherOk:
    def __init__(self):
        self.called_with = None

    def publish_plan(self, *, plan_id, athlete_name, workouts, start_date, folder_name):
        self.called_with = {
            "plan_id": plan_id,
            "athlete_name": athlete_name,
            "workouts_len": len(workouts),
            "start_date": start_date,
            "folder_name": folder_name,
        }
        return PlanPublishResult(
            total_workouts=len(workouts),
            skipped_rest_workouts=0,
            published_workouts=len(workouts),
        )


class _FakePublisherFail:
    def publish_plan(self, *, plan_id, athlete_name, workouts, start_date, folder_name):
        raise RuntimeError("Falla simulada de Selenium")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_and_apply_marks_plan_as_applied(db_session):
    repo = PlanRepository(db_session)
    plan = await repo.create(
        athlete_id="ath-1",
        athlete_name="Atleta Test",
        athlete_context={},
        weeks=4,
        start_date=None,
    )
    await repo.update_status(plan.id, "review")
    await db_session.commit()

    use_cases = PlanUseCases(db_session)
    publisher = _FakePublisherOk()

    dto = PlanApplyRequestDTO(
        workouts=[
            PlanWorkoutDTO(
                day=1,
                week=1,
                date="2026-01-01",
                workout_type="Run",
                title="Rodaje",
                description="Suave",
                pre_activity_comments="Mantén Z2",
                duration="0:45:00",
                distance="10",
                tss=50,
                intensity_factor=0.75,
            )
        ],
        folder_name=None,
    )

    updated = await use_cases.approve_and_apply_plan(plan.id, dto, publisher=publisher)

    assert updated.status == "applied"
    assert publisher.called_with is not None
    assert publisher.called_with["athlete_name"] == "Atleta Test"
    assert publisher.called_with["workouts_len"] == 1
    assert publisher.called_with["folder_name"] == "Neuronomy"

    reloaded = await repo.get_by_id(plan.id)
    assert reloaded is not None
    assert reloaded.status == "applied"
    assert reloaded.approved_at is not None
    assert reloaded.applied_at is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_and_apply_does_not_apply_on_publisher_failure(db_session):
    repo = PlanRepository(db_session)
    plan = await repo.create(
        athlete_id="ath-1",
        athlete_name="Atleta Test",
        athlete_context={},
        weeks=4,
        start_date=None,
    )
    await repo.update_status(plan.id, "review")
    await db_session.commit()

    use_cases = PlanUseCases(db_session)
    publisher = _FakePublisherFail()

    dto = PlanApplyRequestDTO(
        workouts=[
            PlanWorkoutDTO(
                day=1,
                week=1,
                date="2026-01-01",
                workout_type="Run",
                title="Rodaje",
            )
        ]
    )

    with pytest.raises(RuntimeError):
        await use_cases.approve_and_apply_plan(plan.id, dto, publisher=publisher)

    reloaded = await repo.get_by_id(plan.id)
    assert reloaded is not None
    assert reloaded.status == "review"
    assert reloaded.applied_at is None


