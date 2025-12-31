from typing import List
from fastapi import APIRouter, Depends

from app.application.dto.athlete_dto import AthleteDTO
from app.application.use_cases.athlete_use_cases import AthleteUseCases
from app.api.v1.dependencies.use_case_deps import get_athlete_use_cases

router = APIRouter(prefix="/athletes", tags=["Athletes"])


@router.get("/", response_model=List[AthleteDTO])
async def get_all_athletes(
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
):
    """
    Obtener todos los atletas (sincronizados de Airtable).
    """
    return await use_cases.get_all_athletes()


@router.get("/{athlete_id}", response_model=AthleteDTO)
async def get_athlete(
    athlete_id: str, 
    use_cases: AthleteUseCases = Depends(get_athlete_use_cases)
):
    """
    Obtener un atleta por Airtable Record ID.
    """
    return await use_cases.get_athlete(athlete_id)