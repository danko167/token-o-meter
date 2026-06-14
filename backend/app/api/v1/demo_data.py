from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import DemoProgressDep, ExecutionServiceDep, RunStoreDep, ScenarioStoreDep
from app.core.config import get_settings
from app.schemas.scenario import ScenarioFamily
from app.services.demo_data import DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO, DemoDataService
from app.services.llm_models import has_known_pricing

router = APIRouter(prefix="/demo-data", tags=["demo-data"])


class DemoDataResult(BaseModel):
    created: int = 0
    deleted: int = 0
    skipped: int = 0


class DemoExecutionStatus(BaseModel):
    running: bool
    done: bool
    current: int
    total: int
    message: str
    error: str | None = None


class DemoExecuteRequest(BaseModel):
    llm_model: str | None = None
    scenario_families: list[ScenarioFamily] | None = None
    runs_per_runner_per_scenario: int = Field(
        default=DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO,
        ge=1,
        le=20,
    )


class DemoSeedRequest(BaseModel):
    scenario_families: list[ScenarioFamily] | None = None
    runs_per_runner_per_scenario: int = Field(
        default=DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO,
        ge=1,
        le=20,
    )


@router.post("", response_model=DemoDataResult)
def add_demo_data(
    store: RunStoreDep,
    scenarios: ScenarioStoreDep,
    progress: DemoProgressDep,
    request: DemoSeedRequest | None = None,
) -> DemoDataResult:
    runs_per_runner = (
        request.runs_per_runner_per_scenario
        if request
        else DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO
    )
    return DemoDataResult(
        **DemoDataService(store).seed(
            scenarios,
            progress,
            runs_per_runner_per_scenario=runs_per_runner,
            scenario_families=request.scenario_families if request else None,
        )
    )


@router.post("/execute", response_model=DemoDataResult)
async def execute_demo_data(
    store: RunStoreDep,
    scenarios: ScenarioStoreDep,
    execution: ExecutionServiceDep,
    progress: DemoProgressDep,
    request: DemoExecuteRequest | None = None,
) -> DemoDataResult:
    llm_model = request.llm_model if request else None
    runs_per_runner = (
        request.runs_per_runner_per_scenario
        if request
        else DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO
    )
    if llm_model is not None and not has_known_pricing(llm_model, get_settings()):
        raise HTTPException(status_code=400, detail=f"Unknown llm_model: {llm_model}")
    return DemoDataResult(
        **await DemoDataService(store).execute(
            scenarios,
            execution,
            progress,
            llm_model=llm_model,
            runs_per_runner_per_scenario=runs_per_runner,
            scenario_families=request.scenario_families if request else None,
        )
    )


@router.get("/execute/status", response_model=DemoExecutionStatus)
async def get_demo_execution_status(progress: DemoProgressDep) -> DemoExecutionStatus:
    return DemoExecutionStatus(**progress.snapshot())


@router.delete("", response_model=DemoDataResult)
async def delete_demo_data(store: RunStoreDep) -> DemoDataResult:
    return DemoDataResult(deleted=DemoDataService(store).delete())
