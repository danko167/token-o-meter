"""Aggregate human checkpoint and approval metrics from persisted runs."""

from app.schemas.human_metrics import HumanMetricsResult
from app.schemas.run import RunResult
from app.schemas.scenario import ScenarioFamily
from app.services.execution import RunStore


class HumanMetricsService:
    def __init__(self, store: RunStore) -> None:
        self._store = store

    def summarize(
        self,
        scenario_id: str | None = None,
        family: ScenarioFamily | None = None,
    ) -> HumanMetricsResult:
        if scenario_id is not None:
            runs = self._store.list(scenario_id=scenario_id)
        elif family is not None:
            runs = self._store.list(scenario_family=family)
        else:
            runs = self._store.list()

        total = len(runs)
        checkpointed = [run for run in runs if was_checkpointed(run)]
        approved = [run for run in checkpointed if run.output.get("approval_decision") == "approve"]
        rejected = [run for run in checkpointed if run.output.get("approval_decision") == "reject"]
        pending = [run for run in runs if run.status == "pending_approval"]
        escalated = [run for run in runs if _was_escalated(run)]

        totals_by_runner: dict[str, int] = {}
        checkpoints_by_runner: dict[str, int] = {}
        for run in runs:
            totals_by_runner[run.runner] = totals_by_runner.get(run.runner, 0) + 1
            if was_checkpointed(run):
                checkpoints_by_runner[run.runner] = checkpoints_by_runner.get(run.runner, 0) + 1

        intervention_rate_by_runner = {
            runner: round(checkpoints_by_runner.get(runner, 0) / count, 3)
            for runner, count in totals_by_runner.items()
        }

        return HumanMetricsResult(
            scenario_id=scenario_id,
            total_runs=total,
            checkpointed_runs=len(checkpointed),
            approved_runs=len(approved),
            rejected_runs=len(rejected),
            pending_runs=len(pending),
            escalated_runs=len(escalated),
            checkpoint_rate=_rate(len(checkpointed), total),
            approval_rate=_rate(len(approved), len(checkpointed)),
            rejection_rate=_rate(len(rejected), len(checkpointed)),
            escalation_rate=_rate(len(escalated), total),
            intervention_rate_by_runner=intervention_rate_by_runner,
            totals_by_runner=totals_by_runner,
        )


def was_checkpointed(run: RunResult) -> bool:
    return run.pending_approval is not None or any(
        event.kind in {"checkpoint", "decision"} for event in run.trace.events
    )


def _was_escalated(run: RunResult) -> bool:
    return any("escalate" in action or action == "request_changes" for action in run.actions)


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)
