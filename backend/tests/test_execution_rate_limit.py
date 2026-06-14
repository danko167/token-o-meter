import pytest

from app.runners.base import RunnerRegistry
from app.schemas.run import RunnerInfo, RunnerOutput
from app.schemas.scenario import Scenario
from app.services.execution import (
    PROVIDER_RATE_LIMIT_MESSAGE,
    ExecutionService,
    RunStore,
)


@pytest.mark.anyio
async def test_later_llm_backed_runs_are_persisted_as_skipped_after_rate_limit(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    registry = RunnerRegistry()
    registry.register(RateLimitedRunner("llm"))
    tool = CountingRunner("tool")
    registry.register(tool)
    service = ExecutionService(registry, store)
    scenario = Scenario(id="rate-limited", name="Rate limited", input="hello")

    llm = await service.run(scenario, "llm")
    skipped = await service.run(scenario, "tool")

    assert llm.status == "failed"
    assert llm.error == PROVIDER_RATE_LIMIT_MESSAGE
    assert skipped.status == "failed"
    assert skipped.error == f"Skipped: {PROVIDER_RATE_LIMIT_MESSAGE}"
    assert tool.calls == 0
    assert [run.run_id for run in store.list()] == [skipped.run_id, llm.run_id]


@pytest.mark.anyio
async def test_rate_limit_cooldown_is_scoped_to_selected_provider(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    registry = RunnerRegistry()
    registry.register(RateLimitedRunner("llm"))
    tool = CountingRunner("tool")
    registry.register(tool)
    service = ExecutionService(registry, store)
    scenario = Scenario(id="rate-limited", name="Rate limited", input="hello")

    llm = await service.run(scenario, "llm")
    openai_tool = await service.run(
        scenario,
        "tool",
        llm_model="openai:gpt-4.1-mini",
    )

    assert llm.status == "failed"
    assert llm.error == PROVIDER_RATE_LIMIT_MESSAGE
    assert openai_tool.status == "succeeded"
    assert openai_tool.error is None
    assert tool.calls == 1


class RateLimitedRunner:
    level = 2
    description = "fake rate-limited runner"

    def __init__(self, name: str) -> None:
        self.name = name

    def info(self) -> RunnerInfo:
        return RunnerInfo(name=self.name, level=self.level, description=self.description)

    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput:
        raise RuntimeError("RateLimitError: Error code: 429")


class CountingRunner:
    level = 3
    description = "fake counting runner"

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    def info(self) -> RunnerInfo:
        return RunnerInfo(name=self.name, level=self.level, description=self.description)

    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput:
        self.calls += 1
        return RunnerOutput(output={}, actions=[])
