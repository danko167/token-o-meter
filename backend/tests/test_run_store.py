from datetime import UTC, datetime

from app.schemas.run import (
    Evaluation,
    EvaluationCheck,
    Metrics,
    PendingApproval,
    RunResult,
    RunTrace,
    TraceEvent,
)
from app.services.execution import RunStore


def test_run_store_persists_runs_across_instances(tmp_path):
    database_path = tmp_path / "runs.sqlite3"
    first = RunStore(database_path)
    run = RunResult(
        run_id="run-123",
        scenario_id="policy-refund-window",
        runner="rules",
        status="succeeded",
        output={"policy_id": "refund-policy"},
        actions=[],
        metrics=Metrics(duration_ms=1.2),
        created_at=datetime.now(UTC),
    )

    first.add(run)

    second = RunStore(database_path)
    loaded = second.get("run-123")

    assert loaded is not None
    assert loaded.run_id == "run-123"
    assert loaded.output == {"policy_id": "refund-policy"}
    assert second.list()[0].run_id == "run-123"


def test_run_store_round_trips_evaluation_and_pending_approval(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    run = RunResult(
        run_id="run-456",
        scenario_id="customer-email-triage",
        runner="human_checkpoint",
        status="pending_approval",
        output={"intent": "billing_issue"},
        actions=[],
        metrics=Metrics(duration_ms=5.0, prompt_tokens=10, completion_tokens=20),
        evaluation=Evaluation(
            score=80,
            checks=[EvaluationCheck(name="has_intent", passed=True, detail="ok")],
        ),
        pending_approval=PendingApproval(
            action="escalate_billing_review",
            reason="needs human sign-off",
            details={"order_id": "1234"},
        ),
        trace=RunTrace(
            events=[
                TraceEvent(
                    name="Runner execution",
                    kind="runner",
                    timestamp=datetime.now(UTC),
                    duration_ms=5.0,
                    details={"actions": []},
                )
            ]
        ),
        created_at=datetime.now(UTC),
    )

    store.add(run)
    loaded = store.get("run-456")

    assert loaded is not None
    assert loaded.evaluation == run.evaluation
    assert loaded.pending_approval == run.pending_approval
    assert loaded.trace == run.trace
    assert loaded.created_at == run.created_at


def test_run_store_round_trips_human_evaluation(tmp_path):
    from app.schemas.run import HumanEvaluation

    store = RunStore(tmp_path / "runs.sqlite3")
    created_at = datetime.now(UTC)
    run = RunResult(
        run_id="run-human",
        scenario_id="customer-email-triage",
        runner="rules",
        status="succeeded",
        output={"intent": "billing_issue"},
        actions=[],
        metrics=Metrics(),
        human_evaluation=HumanEvaluation(
            score=4,
            useful=True,
            correct=True,
            comment="Useful answer",
            created_at=created_at,
        ),
        created_at=created_at,
    )

    store.add(run)
    loaded = store.get("run-human")

    assert loaded is not None
    assert loaded.human_evaluation == run.human_evaluation


def test_run_store_list_filters_by_scenario_id_and_family(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(_make_run("run-policy", scenario_id="policy-refund-window", scenario_family="policy_qa"))
    store.add(_make_run("run-customer", scenario_id="customer-email-triage", scenario_family="customer_support"))
    store.add(_make_run("run-customer-2", scenario_id="customer-email-triage", scenario_family="customer_support"))

    assert [run.run_id for run in store.list(scenario_id="policy-refund-window")] == ["run-policy"]
    assert {run.run_id for run in store.list(scenario_family="customer_support")} == {
        "run-customer",
        "run-customer-2",
    }
    assert len(store.list()) == 3


def test_run_store_has_pending_runs_for_scenario(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(_make_run("run-pending", scenario_id="policy-refund-window", status="pending_approval"))
    store.add(_make_run("run-done", scenario_id="customer-email-triage", status="succeeded"))

    assert store.has_pending_runs_for_scenario("policy-refund-window") is True
    assert store.has_pending_runs_for_scenario("customer-email-triage") is False
    assert store.has_pending_runs_for_scenario("unknown-scenario") is False


def _make_run(
    run_id: str,
    scenario_id: str = "customer-email-triage",
    scenario_family: str | None = None,
    status: str = "succeeded",
) -> RunResult:
    return RunResult(
        run_id=run_id,
        scenario_id=scenario_id,
        scenario_family=scenario_family,
        runner="rules",
        status=status,
        output={},
        actions=[],
        metrics=Metrics(),
        created_at=datetime.now(UTC),
    )


def test_run_store_delete_removes_runs(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(_make_run("run-a"))
    store.add(_make_run("run-b"))

    deleted = store.delete(["run-a"])

    assert deleted == 1
    assert store.get("run-a") is None
    assert store.get("run-b") is not None
    assert [run.run_id for run in store.list()] == ["run-b"]


def test_run_store_set_archived_hides_and_restores_runs(tmp_path):
    store = RunStore(tmp_path / "runs.sqlite3")
    store.add(_make_run("run-a"))
    store.add(_make_run("run-b"))

    archived = store.set_archived(["run-a"], True)

    assert archived == 1
    assert [run.run_id for run in store.list()] == ["run-b"]
    all_ids = {run.run_id: run.archived for run in store.list(include_archived=True)}
    assert all_ids == {"run-a": True, "run-b": False}

    restored = store.set_archived(["run-a"], False)

    assert restored == 1
    assert {run.run_id for run in store.list()} == {"run-a", "run-b"}
