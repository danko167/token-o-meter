"""Seed/delete representative demo runs for dashboards and recommendations."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.runners import hiring_screening, incident_triage
from app.schemas.run import (
    Evaluation,
    EvaluationCheck,
    HumanEvaluation,
    Metrics,
    PendingApproval,
    RunResult,
    RunTrace,
    ToolCallMetric,
    TraceEvent,
)
from app.schemas.scenario import Scenario
from app.schemas.scenario import ScenarioFamily
from app.services.demo_progress import DemoExecutionProgress
from app.services.execution import (
    LLM_BACKED_RUNNERS,
    PROVIDER_RATE_LIMIT_MESSAGE,
    ExecutionService,
    RunStore,
    is_provider_rate_limit_error_text,
)
from app.services.scenario_store import ScenarioStore

logger = logging.getLogger(__name__)

RUNNERS = ["rules", "workflow", "llm", "tool", "agent", "human_checkpoint"]
RUNNER_LABELS = {
    "rules": "Rules",
    "workflow": "Workflow",
    "llm": "LLM",
    "tool": "Tool use",
    "agent": "Agent",
    "human_checkpoint": "Human checkpoint",
}
DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO = 2
MAX_RUNS_PER_RUNNER_PER_SCENARIO = 20


@dataclass(frozen=True)
class DemoOutcome:
    score: int | None
    status: str = "succeeded"
    decision: str | None = None


class DemoDataService:
    def __init__(self, store: RunStore) -> None:
        self._store = store

    def seed(
        self,
        scenarios: ScenarioStore,
        progress: DemoExecutionProgress | None = None,
        runs_per_runner_per_scenario: int = DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO,
        scenario_families: list[ScenarioFamily] | None = None,
    ) -> dict[str, int]:
        runs_per_runner_per_scenario = _bounded_sample_count(runs_per_runner_per_scenario)
        deleted = 0
        count = 0
        batch_id = uuid.uuid4().hex[:8]
        base = datetime.now(UTC) - timedelta(minutes=30)
        scenario_items = _scenario_items(scenarios, scenario_families)
        total = len(scenario_items) * len(RUNNERS) * runs_per_runner_per_scenario
        if progress is not None:
            progress.start(total, "Starting simulated demo history...")
        logger.info(
            "demo data seed started: mode=realistic_history scenarios=%d runners=%d "
            "runs_per_runner_per_scenario=%d families=%s batch_id=%s",
            len(scenario_items),
            len(RUNNERS),
            runs_per_runner_per_scenario,
            ",".join(scenario_families or ["all"]),
            batch_id,
        )
        try:
            for scenario_index, scenario in enumerate(scenario_items):
                logger.info("demo data seed scenario started: scenario=%s", scenario.id)
                for runner_index, runner in enumerate(RUNNERS):
                    runner_label = RUNNER_LABELS[runner]
                    for outcome_index in range(runs_per_runner_per_scenario):
                        if progress is not None:
                            progress.step(
                                count + 1,
                                f"Simulating {scenario.name} -> {runner_label} "
                                f"sample {outcome_index + 1} ({count + 1}/{total})",
                            )
                        outcome = _outcome_for(scenario, runner, outcome_index)
                        logger.info(
                            "demo data seed run: scenario=%s runner=%s sample=%d "
                            "status=%s score=%s",
                            scenario.id,
                            runner,
                            outcome_index + 1,
                            outcome.status,
                            outcome.score if outcome.score is not None else "n/a",
                        )
                        self._store.add(
                            _demo_run(
                                scenario=scenario,
                                runner=runner,
                                outcome=outcome,
                                outcome_index=outcome_index,
                                batch_id=batch_id,
                                created_at=base
                                + timedelta(
                                    minutes=(
                                        scenario_index * 30 + runner_index * 4 + outcome_index
                                    )
                                ),
                            )
                        )
                        count += 1
                logger.info("demo data seed scenario finished: scenario=%s", scenario.id)
        except Exception as exc:
            if progress is not None:
                progress.fail(f"Simulated demo history failed: {exc}")
            raise
        logger.info("demo data seed finished: created=%d deleted=%d", count, deleted)
        if progress is not None:
            progress.finish(f"Added {count} simulated demo runs - demo data ready")
        return {"created": count, "deleted": deleted}

    async def execute(
        self,
        scenarios: ScenarioStore,
        execution: ExecutionService,
        progress: DemoExecutionProgress,
        llm_model: str | None = None,
        runs_per_runner_per_scenario: int = DEFAULT_RUNS_PER_RUNNER_PER_SCENARIO,
        scenario_families: list[ScenarioFamily] | None = None,
    ) -> dict[str, int]:
        runs_per_runner_per_scenario = _bounded_sample_count(runs_per_runner_per_scenario)
        deleted = 0
        count = 0
        skipped = 0
        provider_rate_limited = False
        provider_rate_limit_reason = PROVIDER_RATE_LIMIT_MESSAGE
        scenario_items = _scenario_items(scenarios, scenario_families)
        total = len(scenario_items) * len(RUNNERS) * runs_per_runner_per_scenario
        progress.start(total, "Starting demo execution...")
        logger.info(
            "demo data execution started: scenarios=%d runners=%d "
            "runs_per_runner_per_scenario=%d families=%s",
            len(scenario_items),
            len(RUNNERS),
            runs_per_runner_per_scenario,
            ",".join(scenario_families or ["all"]),
        )
        try:
            for scenario in scenario_items:
                logger.info("demo data execution scenario started: scenario=%s", scenario.id)
                for runner in RUNNERS:
                    for sample_index in range(runs_per_runner_per_scenario):
                        runner_label = RUNNER_LABELS[runner]
                        if provider_rate_limited and runner in LLM_BACKED_RUNNERS:
                            progress.step(
                                count + 1,
                                f"Skipping {runner_label} for {scenario.name} "
                                f"(rate limited) ({count + 1}/{total})",
                            )
                            run = _skipped_rate_limited_run(
                                scenario,
                                runner,
                                sample_index,
                                provider_rate_limit_reason,
                            )
                            self._store.add(run)
                            logger.info(
                                "demo data execution run skipped: scenario=%s runner=%s "
                                "sample=%d reason=%s",
                                scenario.id,
                                runner,
                                sample_index + 1,
                                provider_rate_limit_reason,
                            )
                            count += 1
                            skipped += 1
                            continue

                        progress.step(
                            count + 1,
                            f"Running {scenario.name} -> {runner_label} "
                            f"sample {sample_index + 1} ({count + 1}/{total})",
                        )
                        logger.info(
                            "demo data execution run started: scenario=%s runner=%s sample=%d",
                            scenario.id,
                            runner,
                            sample_index + 1,
                        )
                        run_llm_model = llm_model if runner in LLM_BACKED_RUNNERS else None
                        run = await execution.run(
                            scenario, runner, llm_model=run_llm_model, is_demo=True
                        )
                        if (
                            runner in LLM_BACKED_RUNNERS
                            and is_provider_rate_limit_error_text(run.error)
                        ):
                            provider_rate_limited = True
                            provider_rate_limit_reason = run.error.removeprefix("Skipped: ")
                            logger.info(
                                "demo data execution detected provider rate limit; remaining "
                                "LLM-backed demo runners will be skipped"
                            )
                        logger.info(
                            "demo data execution run finished: scenario=%s runner=%s "
                            "sample=%d run_id=%s status=%s score=%s duration_ms=%.1f "
                            "cost_usd=%.6f",
                            scenario.id,
                            runner,
                            sample_index + 1,
                            run.run_id,
                            run.status,
                            run.evaluation.score if run.evaluation is not None else "n/a",
                            run.metrics.duration_ms,
                            run.metrics.estimated_cost_usd,
                        )
                        count += 1
                logger.info("demo data execution scenario finished: scenario=%s", scenario.id)
        except Exception as exc:
            progress.fail(f"Demo execution failed: {exc}")
            raise
        logger.info(
            "demo data execution finished: created=%d deleted=%d skipped=%d",
            count,
            deleted,
            skipped,
        )
        finish_message = f"Added {count} demo runs - demo data ready"
        if skipped:
            finish_message += f" ({skipped} skipped due to provider rate limit)"
        progress.finish(finish_message)
        return {"created": count, "deleted": deleted, "skipped": skipped}

    def delete(self) -> int:
        deleted = self._store.delete_demo_runs()
        logger.info("demo data delete finished: deleted=%d", deleted)
        return deleted


def _bounded_sample_count(value: int) -> int:
    return max(1, min(value, MAX_RUNS_PER_RUNNER_PER_SCENARIO))


def _scenario_items(
    scenarios: ScenarioStore,
    scenario_families: list[ScenarioFamily] | None = None,
) -> list[Scenario]:
    allowed = set(scenario_families) if scenario_families else None
    return [
        scenarios.get(summary.id)
        for summary in scenarios.list()
        if allowed is None or summary.family in allowed
    ]


def _outcome_for(scenario: Scenario, runner: str, outcome_index: int) -> DemoOutcome:
    family = scenario.family
    if runner == "human_checkpoint":
        if outcome_index % 5 == 2 or (
            outcome_index == 1 and sum(ord(char) for char in scenario.id) % 2 == 0
        ):
            return DemoOutcome(None, "pending_approval")
        if outcome_index % 5 == 4 or outcome_index == 1:
            return DemoOutcome(86 if family != "customer_support" else 92, decision="reject")
        return DemoOutcome(100 if outcome_index % 2 == 0 else 94, decision="approve")
    if runner == "llm" and outcome_index % 4 == 1:
        return DemoOutcome(None, "failed")
    if runner in {"rules", "workflow"} and family == "git_diff_review":
        score = 62 + outcome_index * 4 if runner == "rules" else 74 + outcome_index * 3
        return DemoOutcome(_bounded_score(score))
    if runner == "rules" and family == "policy_qa":
        return DemoOutcome(_bounded_score(70 + outcome_index * 3))
    base_scores = {
        "rules": 96,
        "workflow": 98,
        "llm": 86,
        "tool": 98,
        "agent": 99,
    }
    score = base_scores.get(runner, 94) - (outcome_index % 3) * 2
    return DemoOutcome(_bounded_score(score))


def _bounded_score(value: int) -> int:
    return max(0, min(value, 100))


def _demo_run(
    scenario: Scenario,
    runner: str,
    outcome: DemoOutcome,
    outcome_index: int,
    batch_id: str,
    created_at: datetime,
) -> RunResult:
    level = RUNNERS.index(runner)
    score = outcome.score or 0
    status = outcome.status
    actions = _actions_for(scenario, runner, status)
    output = _output_for(scenario, runner)
    pending = None
    human_evaluation = None
    if status == "pending_approval":
        pending = PendingApproval(
            action=actions[0] if actions else "provide_policy_answer",
            reason="Demo run waiting for approval.",
            details=output,
        )
        actions = []
    elif status == "succeeded" and outcome.decision is not None:
        output = {**output, "approval_decision": outcome.decision}
        if outcome.decision == "reject":
            output["proposed_action"] = actions[0] if actions else None
            actions = [_fallback_action_for(scenario)]
    if status == "succeeded" and runner in {"agent", "human_checkpoint"}:
        human_evaluation = HumanEvaluation(
            score=5 if score >= 90 else 4,
            useful=True,
            correct=score >= 80,
            comment="Seeded demo rating from a reviewer walkthrough.",
            created_at=created_at + timedelta(seconds=20),
        )

    return RunResult(
        run_id=f"demo-{batch_id}-{scenario.id}-{runner}-{outcome_index + 1}",
        scenario_id=scenario.id,
        scenario_family=scenario.family,
        runner=runner,
        status=status,
        is_demo=True,
        output=output,
        actions=actions,
        error=(
            "Demo failure: model response missed required evidence."
            if status == "failed"
            else None
        ),
        metrics=Metrics(
            duration_ms=round(12 + level * 180 + len(scenario.id), 1),
            prompt_tokens=0 if level < 2 else 80 + level * 45,
            completion_tokens=0 if level < 2 else 30 + level * 20,
            estimated_cost_usd=0.0 if level < 2 else round(0.00004 * level, 6),
            retries=1 if runner == "llm" and score < 80 else 0,
            tool_calls=_tool_calls_for(scenario, runner),
        ),
        evaluation=_evaluation_for(score) if status == "succeeded" else None,
        human_evaluation=human_evaluation,
        pending_approval=pending,
        trace=RunTrace(events=_trace_for(scenario, runner, created_at, status, outcome)),
        created_at=created_at,
    )


def _skipped_rate_limited_run(
    scenario: Scenario,
    runner: str,
    sample_index: int = 0,
    reason: str = PROVIDER_RATE_LIMIT_MESSAGE,
) -> RunResult:
    created_at = datetime.now(UTC)
    return RunResult(
        run_id=(
            f"demo-{scenario.id}-{runner}-skipped-{sample_index + 1}-"
            f"{created_at.timestamp():.0f}"
        ),
        scenario_id=scenario.id,
        scenario_family=scenario.family,
        runner=runner,
        status="failed",
        is_demo=True,
        error=f"Skipped: {reason}",
        metrics=Metrics(),
        trace=RunTrace(
            events=[
                TraceEvent(
                    name="Runner skipped",
                    kind="error",
                    timestamp=created_at,
                    details={"error": reason},
                )
            ]
        ),
        created_at=created_at,
    )


def _output_for(scenario: Scenario, runner: str) -> dict:
    if scenario.family == "customer_support":
        output = {
            "intent": "billing_issue",
            "order_id": "1234",
            "customer_email": "jane.doe@example.com",
        }
        if runner in {"tool", "agent", "human_checkpoint"}:
            output["order_status"] = "delivered, charged twice"
        return output
    if scenario.family == "policy_qa":
        output = {
            "policy_id": "refund-policy",
            "answer": "Defective items are refundable within 30 days.",
        }
        if runner in {"tool", "agent", "human_checkpoint"}:
            output["citations"] = ["refund-policy"]
        return output
    if scenario.family == "incident_triage":
        output = {
            "severity": "high",
            "category": "deployment_regression",
            "summary": incident_triage.SUMMARY_TEMPLATES["deployment_regression"],
        }
        if runner in {"tool", "agent", "human_checkpoint"}:
            output["service"] = "checkout-api"
        return output
    if scenario.family == "hiring_screening":
        output = {
            "decision": "advance_to_interview",
            "match_score": 90,
            "matched_requirements": ["Python", "AWS", "PostgreSQL", "Kubernetes"],
            "missing_requirements": ["On-call rotation experience"],
        }
        if runner in {"tool", "agent", "human_checkpoint"}:
            output["summary"] = "Strong match on required skills; advance to interview."
        return output
    return {
        "verdict": "request_changes" if runner != "rules" else "comment",
        "findings": [
            {"category": "security", "severity": "blocker", "message": "Hardcoded secret."}
        ],
        "summary": "Demo review found a secret in the diff.",
    }


def _actions_for(scenario: Scenario, runner: str, status: str) -> list[str]:
    if status == "failed":
        return []
    if scenario.family == "customer_support":
        return ["escalate_billing_review"]
    if scenario.family == "policy_qa":
        return ["provide_policy_answer"]
    if scenario.family == "incident_triage":
        return ["rollback_deploy"]
    if scenario.family == "hiring_screening":
        return ["advance_to_interview"]
    return ["request_changes"] if status != "succeeded" or runner != "rules" else ["comment_on_pr"]


def _fallback_action_for(scenario: Scenario) -> str:
    if scenario.family == "policy_qa":
        return "escalate_policy_review"
    if scenario.family == "git_diff_review":
        return "escalate_security_review"
    if scenario.family == "incident_triage":
        return incident_triage.REJECT_ACTION
    if scenario.family == "hiring_screening":
        return hiring_screening.REJECT_ACTION
    return "escalate_general_review"


def _evaluation_for(score: int) -> Evaluation:
    return Evaluation(
        score=score,
        checks=[
            EvaluationCheck(
                name="demo.quality",
                passed=score >= 80,
                detail=f"seed score {score}",
            ),
            EvaluationCheck(name="demo.schema", passed=True, detail="representative output"),
        ],
    )


def _tool_calls_for(scenario: Scenario, runner: str) -> list[ToolCallMetric]:
    if runner not in {"tool", "agent", "human_checkpoint"}:
        return []
    if scenario.family == "customer_support":
        return [ToolCallMetric(name="lookup_order", duration_ms=42.0, found=True)]
    if scenario.family == "policy_qa":
        return [ToolCallMetric(name="search_policy", duration_ms=55.0, found=True)]
    if scenario.family == "incident_triage":
        return [ToolCallMetric(name="check_service_status", duration_ms=47.0, found=True)]
    if scenario.family == "hiring_screening":
        return [ToolCallMetric(name="lookup_role_requirements", duration_ms=33.0, found=True)]
    return [
        ToolCallMetric(
            name="read_file",
            duration_ms=38.0,
            found=True,
            details={"path": "app.py"},
        )
    ]


def _trace_for(
    scenario: Scenario,
    runner: str,
    created_at: datetime,
    status: str,
    outcome: DemoOutcome,
) -> list[TraceEvent]:
    events = [
        TraceEvent(name="Request received", kind="request", timestamp=created_at),
        TraceEvent(
            name="Runner execution",
            kind="runner",
            timestamp=created_at + timedelta(seconds=1),
            duration_ms=100,
            details={"demo": True, "runner": runner},
        ),
    ]
    for call in _tool_calls_for(scenario, runner):
        events.append(
            TraceEvent(
                name=f"Tool: {call.name}",
                kind="tool",
                timestamp=created_at + timedelta(seconds=2),
                duration_ms=call.duration_ms,
                details=call.model_dump(),
            )
        )
    if status == "failed":
        events.append(
            TraceEvent(
                name="Runner failed",
                kind="error",
                timestamp=created_at + timedelta(seconds=3),
                details={"error": "Demo failure: model response missed required evidence."},
            )
        )
    else:
        events.append(
            TraceEvent(
                name="Evaluation",
                kind="evaluation",
                timestamp=created_at + timedelta(seconds=3),
                details={"score": outcome.score},
            )
        )
    if runner in {"agent", "human_checkpoint"}:
        events.insert(
            1,
            TraceEvent(
                name="Graph node: plan",
                kind="runner",
                timestamp=created_at,
                details={"node": "plan"},
            ),
        )
        events.insert(
            2,
            TraceEvent(
                name="Graph node: decide",
                kind="runner",
                timestamp=created_at,
                details={"node": "decide"},
            ),
        )
    if outcome.decision is not None:
        events.append(
            TraceEvent(
                name="Human decision",
                kind="decision",
                timestamp=created_at + timedelta(seconds=4),
                details={"decision": outcome.decision},
            )
        )
    if status == "pending_approval":
        events.append(
            TraceEvent(
                name="Human checkpoint",
                kind="checkpoint",
                timestamp=created_at + timedelta(seconds=4),
            )
        )
    return events
