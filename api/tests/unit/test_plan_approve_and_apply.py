"""
Tests para approve_and_apply_plan.

Estos tests verifican que:
- Se use tp_name del atleta (no plan.athlete_name) para seleccionar en TrainingPeaks
- Falle si el atleta no tiene tp_name configurado
- Falle si el atleta no existe en la BD
"""
import pytest

from app.application.dto.plan_dto import PlanApplyRequestDTO, PlanWorkoutDTO
from app.application.use_cases.plan_use_cases import PlanUseCases
from app.application.interfaces.trainingpeaks_plan_publisher import PlanPublishResult
from app.infrastructure.repositories.plan_repository import PlanRepository
from app.infrastructure.repositories.athlete_repository import AthleteRepository


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
    # Crear atleta primero (requerido por el nuevo flujo)
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create({
        "id": "ath-1",
        "name": "Atleta Test",
        "tp_name": "Atleta Test TP",  # tp_name es requerido
        "training_status": "Plan activo",
    })
    await db_session.commit()
    
    repo = PlanRepository(db_session)
    plan = await repo.create(
        athlete_id=athlete.id,
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
    # Ahora debe usar tp_name, no athlete_name del plan
    assert publisher.called_with["athlete_name"] == "Atleta Test TP"
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
    # Crear atleta primero (requerido por el nuevo flujo)
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create({
        "id": "ath-fail-test",
        "name": "Atleta Fail Test",
        "tp_name": "Atleta Fail TP",  # tp_name es requerido
        "training_status": "Plan activo",
    })
    await db_session.commit()
    
    repo = PlanRepository(db_session)
    plan = await repo.create(
        athlete_id=athlete.id,
        athlete_name="Atleta Fail Test",
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


# =============================================================================
# Tests para verificar uso de tp_name
# =============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_and_apply_uses_tp_name_not_athlete_name(db_session):
    """
    Verifica que se use athlete.tp_name para seleccionar en TrainingPeaks,
    NO plan.athlete_name.
    """
    # Crear atleta con tp_name diferente al nombre del plan
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create({
        "id": "ath-tp-test",
        "name": "Nombre En BD",
        "tp_name": "Nombre En TrainingPeaks",  # Este es el que se debe usar
        "training_status": "Plan activo",
    })
    await db_session.commit()
    
    # Crear plan con athlete_name diferente a tp_name
    plan_repo = PlanRepository(db_session)
    plan = await plan_repo.create(
        athlete_id=athlete.id,
        athlete_name="Nombre En Plan",  # Este NO se debe usar
        athlete_context={},
        weeks=4,
        start_date=None,
    )
    await plan_repo.update_status(plan.id, "review")
    await db_session.commit()

    use_cases = PlanUseCases(db_session)
    publisher = _FakePublisherOk()

    dto = PlanApplyRequestDTO(
        workouts=[
            PlanWorkoutDTO(
                day=1, week=1, date="2026-01-01",
                workout_type="Run", title="Test"
            )
        ]
    )

    await use_cases.approve_and_apply_plan(plan.id, dto, publisher=publisher)

    # Verificar que se uso tp_name, NO athlete_name del plan
    assert publisher.called_with is not None
    assert publisher.called_with["athlete_name"] == "Nombre En TrainingPeaks"
    assert publisher.called_with["athlete_name"] != "Nombre En Plan"
    assert publisher.called_with["athlete_name"] != "Nombre En BD"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_and_apply_fails_if_no_tp_name(db_session):
    """
    Verifica que falle si el atleta no tiene tp_name configurado.
    """
    # Crear atleta SIN tp_name
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create({
        "id": "ath-no-tp",
        "name": "Atleta Sin TP",
        "tp_name": None,  # Sin tp_name
        "training_status": "Plan activo",
    })
    await db_session.commit()
    
    # Crear plan
    plan_repo = PlanRepository(db_session)
    plan = await plan_repo.create(
        athlete_id=athlete.id,
        athlete_name="Atleta Sin TP",
        athlete_context={},
        weeks=4,
        start_date=None,
    )
    await plan_repo.update_status(plan.id, "review")
    await db_session.commit()

    use_cases = PlanUseCases(db_session)
    publisher = _FakePublisherOk()

    dto = PlanApplyRequestDTO(
        workouts=[
            PlanWorkoutDTO(
                day=1, week=1, date="2026-01-01",
                workout_type="Run", title="Test"
            )
        ]
    )

    # Debe fallar con error indicando que falta tp_name
    with pytest.raises(ValueError) as exc_info:
        await use_cases.approve_and_apply_plan(plan.id, dto, publisher=publisher)
    
    assert "tp_name" in str(exc_info.value)
    assert "sincronizacion" in str(exc_info.value).lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_approve_and_apply_fails_if_athlete_not_found(db_session):
    """
    Verifica que falle si el atleta no existe en la BD.
    """
    # Crear plan con athlete_id que no existe
    plan_repo = PlanRepository(db_session)
    plan = await plan_repo.create(
        athlete_id="atleta-inexistente",
        athlete_name="Fantasma",
        athlete_context={},
        weeks=4,
        start_date=None,
    )
    await plan_repo.update_status(plan.id, "review")
    await db_session.commit()

    use_cases = PlanUseCases(db_session)
    publisher = _FakePublisherOk()

    dto = PlanApplyRequestDTO(
        workouts=[
            PlanWorkoutDTO(
                day=1, week=1, date="2026-01-01",
                workout_type="Run", title="Test"
            )
        ]
    )

    # Debe fallar indicando que el atleta no existe
    with pytest.raises(ValueError) as exc_info:
        await use_cases.approve_and_apply_plan(plan.id, dto, publisher=publisher)
    
    assert "no encontrado" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


