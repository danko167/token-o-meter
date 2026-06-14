from fastapi import APIRouter, HTTPException, Query

from app.api.deps import RunStoreDep, ScenarioStoreDep
from app.schemas.human_metrics import HumanMetricsResult
from app.schemas.scenario import ScenarioFamily
from app.services.human_metrics import HumanMetricsService
from app.services.scenario_store import ScenarioNotFoundError

router = APIRouter(prefix="/human-metrics", tags=["human-metrics"])


@router.get("", response_model=HumanMetricsResult)
async def get_human_metrics(
    store: RunStoreDep,
    scenarios: ScenarioStoreDep,
    scenario_id: str | None = Query(default=None),
    family: ScenarioFamily | None = Query(default=None),
) -> HumanMetricsResult:
    if scenario_id is not None:
        try:
            scenarios.get(scenario_id)
        except ScenarioNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Unknown scenario: {scenario_id}"
            ) from None
        return HumanMetricsService(store).summarize(scenario_id=scenario_id)

    return HumanMetricsService(store).summarize(family=family)
