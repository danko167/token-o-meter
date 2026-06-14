"""Runner contract: every abstraction level implements the same interface
so results are directly comparable."""

from abc import ABC, abstractmethod
from typing import ClassVar

from app.schemas.run import RunnerInfo, RunnerOutput
from app.schemas.scenario import Scenario


class BaseRunner(ABC):
    #: unique key used in API requests, e.g. "rules", "llm"
    name: ClassVar[str]
    #: abstraction level 0-5 (0 = deterministic rules, 5 = human-in-the-loop)
    level: ClassVar[int]
    description: ClassVar[str] = ""

    @abstractmethod
    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput: ...

    async def resume(self, run_id: str, decision: str) -> RunnerOutput:
        """Continue a run that paused with `pending_approval` (Level 5 only)."""
        raise RunnerCannotResumeError(f"'{self.name}' runner does not support resuming a run")

    def info(self) -> RunnerInfo:
        return RunnerInfo(name=self.name, level=self.level, description=self.description)


class RunnerNotFoundError(KeyError):
    pass


class NotImplementedRunnerError(RuntimeError):
    """Raised by runners that are registered but not yet implemented."""


class RunnerCannotResumeError(RuntimeError):
    """Raised when resume() is called on a runner that never pauses."""


class RunnerRegistry:
    def __init__(self) -> None:
        self._runners: dict[str, BaseRunner] = {}

    def register(self, runner: BaseRunner) -> None:
        self._runners[runner.name] = runner

    def get(self, name: str) -> BaseRunner:
        try:
            return self._runners[name]
        except KeyError:
            raise RunnerNotFoundError(name) from None

    def list(self) -> list[RunnerInfo]:
        return [r.info() for r in sorted(self._runners.values(), key=lambda r: r.level)]
