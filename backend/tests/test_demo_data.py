import uuid
from datetime import UTC, datetime

import pytest

from app.schemas.run import Metrics, RunResult
from app.schemas.scenario import Scenario, ScenarioSummary
from app.services.demo_data import LLM_BACKED_RUNNERS, DemoDataService
from app.services.demo_progress import DemoExecutionProgress
from app.services.execution import PROVIDER_RATE_LIMIT_MESSAGE, RunStore


def test_seed_demo_data_is_additive(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    service = DemoDataService(store)

    first = service.seed(FakeScenarioStore(), runs_per_runner_per_scenario=1)
    second = service.seed(FakeScenarioStore(), runs_per_runner_per_scenario=1)

    assert first["created"] == 18
    assert first["deleted"] == 0
    assert second["created"] == 18
    assert second["deleted"] == 0
    assert len([run for run in store.list() if run.is_demo]) == 36


def test_seed_demo_data_filters_selected_scenario_families(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    service = DemoDataService(store)
    progress = DemoExecutionProgress()

    result = service.seed(
        FakeScenarioStore(),
        progress,
        runs_per_runner_per_scenario=1,
        scenario_families=["policy_qa"],
    )

    assert result["created"] == 6
    demo_runs = [run for run in store.list() if run.is_demo]
    assert len(demo_runs) == 6
    assert {run.scenario_family for run in demo_runs} == {"policy_qa"}
    snapshot = progress.snapshot()
    assert snapshot["running"] is False
    assert snapshot["done"] is True
    assert snapshot["current"] == 6
    assert snapshot["total"] == 6


def test_seed_demo_data_clamps_scores_when_many_samples_are_requested(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    service = DemoDataService(store)

    result = service.seed(
        FakeScenarioStore(),
        runs_per_runner_per_scenario=20,
        scenario_families=["git_diff_review"],
    )

    assert result["created"] == 120
    demo_runs = [run for run in store.list() if run.is_demo]
    succeeded_scores = [
        run.evaluation.score
        for run in demo_runs
        if run.evaluation is not None
    ]
    assert succeeded_scores
    assert max(succeeded_scores) == 100


@pytest.mark.anyio
async def test_execute_demo_data_skips_remaining_llm_runners_after_rate_limit(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    execution = RateLimitedExecution()
    progress = DemoExecutionProgress()

    result = await DemoDataService(store).execute(
        FakeScenarioStore(),
        execution,
        progress,
        runs_per_runner_per_scenario=1,
    )

    assert result["created"] == 18
    assert execution.calls == [
        ("customer-email-triage", "rules"),
        ("customer-email-triage", "workflow"),
        ("customer-email-triage", "llm"),
        ("policy-refund-window", "rules"),
        ("policy-refund-window", "workflow"),
        ("diff-hardcoded-secret", "rules"),
        ("diff-hardcoded-secret", "workflow"),
    ]

    runs = store.list()
    skipped = [
        run
        for run in runs
        if run.runner in {"tool", "agent", "human_checkpoint"} and run.status == "failed"
    ]
    assert len(skipped) == 9
    assert all(run.is_demo for run in skipped)
    assert all(run.error and "Skipped:" in run.error for run in skipped)
    # Also includes the "llm" runner skips for the second/third scenarios, on top of
    # the tool/agent/human_checkpoint skips counted above.
    assert result["skipped"] == 11

    snapshot = progress.snapshot()
    assert snapshot["done"] is True
    assert snapshot["running"] is False
    assert snapshot["current"] == 18
    assert snapshot["total"] == 18
    assert snapshot["error"] is None


@pytest.mark.anyio
async def test_execute_demo_data_is_additive(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    service = DemoDataService(store)
    progress = DemoExecutionProgress()

    first = await service.execute(
        FakeScenarioStore(),
        StoringRecordingExecution(store),
        progress,
        runs_per_runner_per_scenario=1,
    )
    second = await service.execute(
        FakeScenarioStore(),
        StoringRecordingExecution(store),
        progress,
        runs_per_runner_per_scenario=1,
    )

    assert first["created"] == 18
    assert first["deleted"] == 0
    assert second["created"] == 18
    assert second["deleted"] == 0
    assert len([run for run in store.list() if run.is_demo]) == 36


@pytest.mark.anyio
async def test_execute_demo_data_filters_selected_scenario_families(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    execution = StoringRecordingExecution(store)
    progress = DemoExecutionProgress()

    result = await DemoDataService(store).execute(
        FakeScenarioStore(),
        execution,
        progress,
        runs_per_runner_per_scenario=1,
        scenario_families=["git_diff_review"],
    )

    assert result["created"] == 6
    assert execution.calls == [
        ("diff-hardcoded-secret", "rules"),
        ("diff-hardcoded-secret", "workflow"),
        ("diff-hardcoded-secret", "llm"),
        ("diff-hardcoded-secret", "tool"),
        ("diff-hardcoded-secret", "agent"),
        ("diff-hardcoded-secret", "human_checkpoint"),
    ]
    snapshot = progress.snapshot()
    assert snapshot["current"] == 6
    assert snapshot["total"] == 6


@pytest.mark.anyio
async def test_execute_demo_data_passes_selected_llm_model_to_llm_backed_runners(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    execution = RecordingExecution()
    progress = DemoExecutionProgress()

    result = await DemoDataService(store).execute(
        FakeScenarioStore(),
        execution,
        progress,
        llm_model="openai:gpt-4.1-mini",
        runs_per_runner_per_scenario=1,
    )

    assert result["created"] == 18
    for (_, runner), llm_model in zip(execution.calls, execution.llm_models, strict=True):
        if runner in LLM_BACKED_RUNNERS:
            assert llm_model == "openai:gpt-4.1-mini"
        else:
            assert llm_model is None


class FakeScenarioStore:
    def list(self) -> list[ScenarioSummary]:
        return [
            ScenarioSummary(
                id="customer-email-triage",
                name="customer-email-triage",
                family="customer_support",
            ),
            ScenarioSummary(
                id="policy-refund-window",
                name="policy-refund-window",
                family="policy_qa",
            ),
            ScenarioSummary(
                id="diff-hardcoded-secret",
                name="diff-hardcoded-secret",
                family="git_diff_review",
            ),
        ]

    def get(self, scenario_id: str) -> Scenario:
        family = "customer_support"
        if scenario_id.startswith("policy-"):
            family = "policy_qa"
        if scenario_id.startswith("diff-"):
            family = "git_diff_review"
        return Scenario(
            id=scenario_id,
            name=scenario_id,
            input="demo",
            family=family,
        )


class RecordingExecution:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.llm_models: list[str | None] = []

    async def run(
        self,
        scenario: Scenario,
        runner: str,
        llm_model: str | None = None,
        is_demo: bool = False,
    ) -> RunResult:
        self.calls.append((scenario.id, runner))
        self.llm_models.append(llm_model)
        return RunResult(
            run_id=f"{scenario.id}-{runner}",
            scenario_id=scenario.id,
            scenario_family=scenario.family,
            runner=runner,
            status="succeeded",
            is_demo=is_demo,
            metrics=Metrics(),
            created_at=datetime.now(UTC),
        )


class StoringRecordingExecution(RecordingExecution):
    def __init__(self, store: RunStore) -> None:
        super().__init__()
        self._store = store
        self._counter = 0
        self._batch_id = uuid.uuid4().hex[:8]

    async def run(
        self,
        scenario: Scenario,
        runner: str,
        llm_model: str | None = None,
        is_demo: bool = False,
    ) -> RunResult:
        run = await super().run(scenario, runner, llm_model, is_demo)
        self._counter += 1
        stored_run = run.model_copy(
            update={"run_id": f"{run.run_id}-{self._batch_id}-{self._counter}"}
        )
        self._store.add(stored_run)
        return stored_run


class RateLimitedExecution:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.llm_models: list[str | None] = []

    async def run(
        self,
        scenario: Scenario,
        runner: str,
        llm_model: str | None = None,
        is_demo: bool = False,
    ) -> RunResult:
        self.calls.append((scenario.id, runner))
        self.llm_models.append(llm_model)
        return RunResult(
            run_id=f"{scenario.id}-{runner}",
            scenario_id=scenario.id,
            scenario_family=scenario.family,
            runner=runner,
            status="failed" if runner == "llm" else "succeeded",
            is_demo=is_demo,
            error=PROVIDER_RATE_LIMIT_MESSAGE if runner == "llm" else None,
            metrics=Metrics(),
            created_at=datetime.now(UTC),
        )
