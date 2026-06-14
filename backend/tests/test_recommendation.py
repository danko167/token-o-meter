from datetime import UTC, datetime

from app.runners.base import RunnerRegistry
from app.runners.rule_runner import RuleRunner
from app.runners.workflow_runner import WorkflowRunner
from app.schemas.run import Evaluation, EvaluationCheck, Metrics, RunResult, RunTrace, TraceEvent
from app.services.execution import RunStore
from app.services.recommendation import RecommendationService


def test_recommendation_picks_lowest_reliable_abstraction(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    registry = RunnerRegistry()
    registry.register(RuleRunner())
    registry.register(WorkflowRunner())
    store.add(_run("run-rules", "rules", score=100, duration_ms=5, cost=0))
    store.add(_run("run-workflow", "workflow", score=100, duration_ms=7, cost=0))

    result = RecommendationService(registry, store).recommend("customer-email-triage")

    assert result.recommended_runner == "rules"
    assert result.recommended_level == 0
    assert result.confidence == 1.0
    assert result.runners[0].reliable is True


def test_recommendation_skips_unreliable_runner(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    registry = RunnerRegistry()
    registry.register(RuleRunner())
    registry.register(WorkflowRunner())
    store.add(_run("run-rules", "rules", score=50, duration_ms=5, cost=0))
    store.add(_run("run-workflow", "workflow", score=100, duration_ms=7, cost=0))

    result = RecommendationService(registry, store).recommend("customer-email-triage")

    assert result.recommended_runner == "workflow"
    rules = next(item for item in result.runners if item.runner == "rules")
    assert rules.reliable is False
    assert any("Average score" in reason for reason in rules.reasons)
    rules_explanation = next(item for item in result.counterfactuals if item.runner == "rules")
    assert rules_explanation.outcome == "not_reliable"
    assert "not recommended" in rules_explanation.summary


def test_recommendation_can_choose_fallback_strategy(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    registry = RunnerRegistry()
    registry.register(RuleRunner())
    registry.register(WorkflowRunner())
    store.add(_run("run-rules", "rules", score=70, duration_ms=5, cost=0))
    store.add(_run("run-workflow", "workflow", score=100, duration_ms=7, cost=0))

    result = RecommendationService(registry, store).recommend("customer-email-triage")

    assert result.strategy == "rules_plus_fallback"
    assert result.primary_runner == "rules"
    assert result.fallback_runner == "workflow"
    assert result.recommended_runner == "workflow"
    assert result.simulation is not None
    assert result.simulation.projected_success_rate == 1.0
    primary_explanation = next(item for item in result.counterfactuals if item.runner == "rules")
    fallback_explanation = next(
        item for item in result.counterfactuals if item.runner == "workflow"
    )
    assert primary_explanation.outcome == "primary"
    assert fallback_explanation.outcome == "fallback"


def test_recommendation_checkpoint_rate_counts_resolved_checkpoints(tmp_path):
    """A run that was checkpointed and then approved/rejected ends up `succeeded`,
    not `pending_approval` - checkpoint_rate must still count it via trace events,
    matching HumanMetricsService's was_checkpointed()."""
    store = RunStore(tmp_path / "runs.sqlite3")
    registry = RunnerRegistry()
    registry.register(RuleRunner())
    registry.register(WorkflowRunner())
    store.add(_run("run-rules", "rules", score=100, duration_ms=5, cost=0))
    store.add(
        _run(
            "run-rules-resumed",
            "rules",
            score=100,
            duration_ms=5,
            cost=0,
            trace=RunTrace(
                events=[
                    TraceEvent(name="Human checkpoint", kind="checkpoint", timestamp=datetime.now(UTC)),
                    TraceEvent(name="Human decision", kind="decision", timestamp=datetime.now(UTC)),
                ]
            ),
        )
    )
    store.add(_run("run-workflow", "workflow", score=100, duration_ms=7, cost=0))

    result = RecommendationService(registry, store).recommend("customer-email-triage")

    rules = next(item for item in result.runners if item.runner == "rules")
    assert rules.checkpoint_rate == 0.5


def test_recommendation_handles_no_runs(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    registry = RunnerRegistry()
    registry.register(RuleRunner())

    result = RecommendationService(registry, store).recommend("customer-email-triage")

    assert result.recommended_runner is None
    assert result.confidence == 0
    assert result.runners[0].reasons == ["No runs recorded.", "No successful evaluated runs."]
    assert result.counterfactuals[0].outcome == "needs_data"


def _run(
    run_id: str,
    runner: str,
    score: int,
    duration_ms: float,
    cost: float,
    trace: RunTrace | None = None,
) -> RunResult:
    return RunResult(
        run_id=run_id,
        scenario_id="customer-email-triage",
        runner=runner,
        status="succeeded",
        output={"intent": "billing_issue", "order_id": "1234"},
        actions=[],
        metrics=Metrics(duration_ms=duration_ms, estimated_cost_usd=cost),
        evaluation=Evaluation(
            score=score,
            checks=[EvaluationCheck(name="expected.intent", passed=score >= 80)],
        ),
        trace=trace if trace is not None else RunTrace(),
        created_at=datetime.now(UTC),
    )
