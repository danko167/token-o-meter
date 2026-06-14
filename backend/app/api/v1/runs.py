from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import ExecutionServiceDep, RunStoreDep, ScenarioStoreDep
from app.core.config import get_settings
from app.runners.base import RunnerCannotResumeError, RunnerNotFoundError
from app.schemas.run import (
    HumanEvaluation,
    HumanEvaluationRequest,
    RunBulkActionResult,
    RunDecisionRequest,
    RunIdsRequest,
    RunListPage,
    RunRequest,
    RunResult,
    RunUsageSummary,
)
from app.services.execution import RunNotFoundError, RunNotResumableError
from app.services.llm_models import has_known_pricing
from app.services.scenario_store import ScenarioNotFoundError

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResult, status_code=201)
async def create_run(
    request: RunRequest,
    scenarios: ScenarioStoreDep,
    execution: ExecutionServiceDep,
) -> RunResult:
    try:
        scenario = scenarios.get(request.scenario_id)
    except ScenarioNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Unknown scenario: {request.scenario_id}"
        ) from None
    if request.llm_model is not None and not has_known_pricing(request.llm_model, get_settings()):
        raise HTTPException(
            status_code=400, detail=f"Unknown llm_model: {request.llm_model}"
        )
    try:
        return await execution.run(scenario, request.runner, llm_model=request.llm_model)
    except RunnerNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Unknown runner: {request.runner}"
        ) from None


@router.get("", response_model=list[RunResult])
async def list_runs(store: RunStoreDep, include_archived: bool = False) -> list[RunResult]:
    return store.list(include_archived=include_archived)


@router.get("/page", response_model=RunListPage)
async def list_runs_page(
    store: RunStoreDep,
    include_archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=10, le=100),
) -> RunListPage:
    if page_size not in {10, 25, 50, 100}:
        raise HTTPException(status_code=422, detail="page_size must be one of 10, 25, 50, 100")
    items, total = store.list_page(
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )
    return RunListPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/latest-by-runner", response_model=list[RunResult])
async def latest_runs_by_runner(
    store: RunStoreDep,
    scenario_id: str,
    include_archived: bool = False,
) -> list[RunResult]:
    return store.latest_by_runner(scenario_id=scenario_id, include_archived=include_archived)


@router.get("/usage-summary", response_model=RunUsageSummary)
async def run_usage_summary(
    store: RunStoreDep,
    include_archived: bool = True,
) -> RunUsageSummary:
    return store.usage_summary(include_archived=include_archived)


@router.post("/bulk-delete", response_model=RunBulkActionResult)
async def bulk_delete_runs(request: RunIdsRequest, store: RunStoreDep) -> RunBulkActionResult:
    return RunBulkActionResult(count=store.delete(request.run_ids))


@router.post("/bulk-archive", response_model=RunBulkActionResult)
async def bulk_archive_runs(request: RunIdsRequest, store: RunStoreDep) -> RunBulkActionResult:
    return RunBulkActionResult(count=store.set_archived(request.run_ids, True))


@router.post("/bulk-unarchive", response_model=RunBulkActionResult)
async def bulk_unarchive_runs(request: RunIdsRequest, store: RunStoreDep) -> RunBulkActionResult:
    return RunBulkActionResult(count=store.set_archived(request.run_ids, False))


@router.get("/{run_id}", response_model=RunResult)
async def get_run(run_id: str, store: RunStoreDep) -> RunResult:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return run


@router.post("/{run_id}/decision", response_model=RunResult)
async def submit_decision(
    run_id: str,
    request: RunDecisionRequest,
    scenarios: ScenarioStoreDep,
    execution: ExecutionServiceDep,
) -> RunResult:
    try:
        return await execution.resume(run_id, request.decision, scenarios)
    except RunNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}") from None
    except RunNotResumableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except RunnerCannotResumeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/{run_id}/human-evaluation", response_model=RunResult)
async def submit_human_evaluation(
    run_id: str,
    request: HumanEvaluationRequest,
    store: RunStoreDep,
) -> RunResult:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")

    updated = run.model_copy(
        update={
            "human_evaluation": HumanEvaluation(
                score=request.score,
                useful=request.useful,
                correct=request.correct,
                comment=request.comment,
                created_at=datetime.now(UTC),
            )
        }
    )
    store.add(updated)
    return updated
