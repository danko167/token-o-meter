from fastapi import APIRouter, HTTPException

from app.api.deps import RegistryDep, RunStoreDep, ScenarioStoreDep
from app.schemas.recommendation import RecommendationResult
from app.services.recommendation import RecommendationService
from app.services.scenario_store import ScenarioNotFoundError

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/{scenario_id}", response_model=RecommendationResult)
async def get_recommendation(
    scenario_id: str,
    scenarios: ScenarioStoreDep,
    registry: RegistryDep,
    store: RunStoreDep,
) -> RecommendationResult:
    try:
        scenarios.get(scenario_id)
    except ScenarioNotFoundError:
        if not store.has_runs_for_scenario(scenario_id):
            raise HTTPException(
                status_code=404, detail=f"Unknown scenario: {scenario_id}"
            ) from None

    return RecommendationService(registry, store).recommend(scenario_id)
