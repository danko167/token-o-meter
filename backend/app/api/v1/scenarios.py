from fastapi import APIRouter, HTTPException

from app.api.deps import RunStoreDep, ScenarioStoreDep
from app.schemas.scenario import Scenario, ScenarioCreate, ScenarioSummary
from app.services.scenario_store import (
    BuiltInScenarioError,
    ScenarioAlreadyExistsError,
    ScenarioNotFoundError,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioSummary])
async def list_scenarios(store: ScenarioStoreDep) -> list[ScenarioSummary]:
    return store.list()


@router.post("", response_model=Scenario, status_code=201)
async def create_scenario(payload: ScenarioCreate, store: ScenarioStoreDep) -> Scenario:
    try:
        return store.create(payload)
    except ScenarioAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"Scenario already exists: {exc}"
        ) from None


@router.get("/{scenario_id}", response_model=Scenario)
async def get_scenario(scenario_id: str, store: ScenarioStoreDep) -> Scenario:
    try:
        return store.get(scenario_id)
    except ScenarioNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Unknown scenario: {scenario_id}"
        ) from None


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: str, store: ScenarioStoreDep, runs: RunStoreDep) -> None:
    if runs.has_pending_runs_for_scenario(scenario_id):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scenario {scenario_id} has runs awaiting a human decision. "
                "Approve or reject them before deleting this scenario."
            ),
        )
    try:
        store.delete_custom(scenario_id)
    except BuiltInScenarioError:
        raise HTTPException(
            status_code=409, detail=f"Built-in scenarios cannot be deleted: {scenario_id}"
        ) from None
    except ScenarioNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Unknown scenario: {scenario_id}"
        ) from None
