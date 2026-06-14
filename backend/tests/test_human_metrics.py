from datetime import UTC, datetime

from app.schemas.run import Metrics, PendingApproval, RunResult, RunTrace, TraceEvent
from app.services.execution import RunStore
from app.services.human_metrics import HumanMetricsService


def test_human_metrics_counts_checkpoints_and_decisions(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(
        RunResult(
            run_id="pending",
            scenario_id="policy",
            runner="human_checkpoint",
            status="pending_approval",
            output={},
            actions=[],
            metrics=Metrics(),
            pending_approval=PendingApproval(action="provide_policy_answer"),
            trace=RunTrace(
                events=[
                    TraceEvent(
                        name="Human checkpoint",
                        kind="checkpoint",
                        timestamp=datetime.now(UTC),
                    )
                ]
            ),
            created_at=datetime.now(UTC),
        )
    )
    store.add(
        RunResult(
            run_id="approved",
            scenario_id="policy",
            runner="human_checkpoint",
            status="succeeded",
            output={"approval_decision": "approve"},
            actions=["provide_policy_answer"],
            metrics=Metrics(),
            trace=RunTrace(
                events=[
                    TraceEvent(name="Human decision", kind="decision", timestamp=datetime.now(UTC))
                ]
            ),
            created_at=datetime.now(UTC),
        )
    )

    metrics = HumanMetricsService(store).summarize("policy")

    assert metrics.total_runs == 2
    assert metrics.checkpointed_runs == 2
    assert metrics.approved_runs == 1
    assert metrics.pending_runs == 1
    assert metrics.checkpoint_rate == 1.0
    assert metrics.approval_rate == 0.5


def test_human_metrics_ignores_approval_decision_without_checkpoint(tmp_path):
    """A run can carry `approval_decision` in its output without ever having been
    checkpointed (e.g. legacy runs predating checkpoint trace events). Such runs
    must not be counted as approved/rejected, or `approval_rate`/`rejection_rate`
    could exceed 1.0."""
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(
        RunResult(
            run_id="checkpointed-approved",
            scenario_id="policy",
            runner="human_checkpoint",
            status="succeeded",
            output={"approval_decision": "approve"},
            actions=["provide_policy_answer"],
            metrics=Metrics(),
            trace=RunTrace(
                events=[
                    TraceEvent(name="Human decision", kind="decision", timestamp=datetime.now(UTC))
                ]
            ),
            created_at=datetime.now(UTC),
        )
    )
    for i in range(5):
        store.add(
            RunResult(
                run_id=f"legacy-approved-{i}",
                scenario_id="policy",
                runner="human_checkpoint",
                status="succeeded",
                output={"approval_decision": "approve"},
                actions=["provide_policy_answer"],
                metrics=Metrics(),
                created_at=datetime.now(UTC),
            )
        )

    metrics = HumanMetricsService(store).summarize("policy")

    assert metrics.total_runs == 6
    assert metrics.checkpointed_runs == 1
    assert metrics.approved_runs == 1
    assert metrics.approval_rate == 1.0


def test_human_metrics_can_filter_by_family(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(
        RunResult(
            run_id="policy-checkpoint",
            scenario_id="policy-refund-window",
            scenario_family="policy_qa",
            runner="human_checkpoint",
            status="pending_approval",
            output={},
            actions=[],
            metrics=Metrics(),
            pending_approval=PendingApproval(action="provide_policy_answer"),
            created_at=datetime.now(UTC),
        )
    )
    store.add(
        RunResult(
            run_id="customer-checkpoint",
            scenario_id="customer-email-triage",
            scenario_family="customer_support",
            runner="human_checkpoint",
            status="pending_approval",
            output={},
            actions=[],
            metrics=Metrics(),
            pending_approval=PendingApproval(action="escalate_billing_review"),
            created_at=datetime.now(UTC),
        )
    )

    metrics = HumanMetricsService(store).summarize(family="policy_qa")

    assert metrics.total_runs == 1
    assert metrics.checkpointed_runs == 1
    assert metrics.pending_runs == 1


def test_human_metrics_family_filter_includes_runs_for_deleted_scenario(tmp_path):
    """A run keeps its scenario_family snapshot even if the scenario that
    produced it is later deleted, so it still counts toward family metrics."""
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(
        RunResult(
            run_id="orphaned-run",
            scenario_id="deleted-custom-scenario",
            scenario_family="policy_qa",
            runner="rules",
            status="succeeded",
            output={},
            actions=[],
            metrics=Metrics(),
            created_at=datetime.now(UTC),
        )
    )

    metrics = HumanMetricsService(store).summarize(family="policy_qa")

    assert metrics.total_runs == 1
