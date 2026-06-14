"""Level 5: agent workflow with a human-in-the-loop approval gate.

Same plan/act/decide loop as AgentRunner (Level 4), but the proposed action
is run through the shared `checkpoint_policy.evaluate()` (see
`app/services/checkpoint_policy.py`) — a risky action, missing required
fields, low model confidence, or retries needed to settle on a response can
each trigger a pause. When triggered, the graph pauses via LangGraph's
`interrupt()` and waits for a human decision before `finalize`. The run comes
back with status `pending_approval`; submit the human's decision via
`POST /runs/{run_id}/decision` to resume it."""

from datetime import UTC, datetime, timedelta
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.runners.base import BaseRunner
from app.runners.families import FAMILY_MODULES
from app.schemas.run import PendingApproval, RunnerOutput
from app.schemas.scenario import Scenario, ScenarioFamily
from app.services import checkpoint_policy
from app.services.checkpoint_policy import DEFAULT_CONFIDENCE_THRESHOLD
from app.services.llm_client import LLMClient

# How long a run may sit in `pending_approval` (or otherwise unresolved)
# before its checkpointer thread and family record are evicted. Bounds the
# memory growth from runs that never receive a decision via resume().
PENDING_RUN_TTL = timedelta(hours=1)


def _evaluate_checkpoint(state: Any, module: Any) -> checkpoint_policy.CheckpointDecision:
    proposed = state["proposed"] or {}
    return checkpoint_policy.evaluate(
        action=proposed.get("action"),
        output=proposed.get("output", {}),
        confidence=proposed.get("confidence"),
        retries=state.get("retries", 0),
        risky_actions=module.RISKY_ACTIONS,
        required_fields=state.get("required_fields", []),
        confidence_threshold=state.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD),
    )


def _make_route_after_decide(module: Any):
    def _route_after_decide(state: Any) -> str:
        return "approval" if _evaluate_checkpoint(state, module).needs_approval else "finalize"

    return _route_after_decide


def _make_approval(module: Any):
    def _approval(state: Any) -> dict[str, Any]:
        proposed = state["proposed"] or {}
        checkpoint = _evaluate_checkpoint(state, module)
        decision = interrupt(
            {
                "action": proposed.get("action"),
                "output": proposed.get("output", {}),
                "confidence": proposed.get("confidence"),
                "reason": checkpoint.reason,
                "details": checkpoint.details,
            }
        )
        return {"approval_decision": decision.get("decision", "reject")}

    return _approval


class HumanCheckpointRunner(BaseRunner):
    name = "human_checkpoint"
    level = 5
    description = (
        "Same LangGraph agent as 'agent', but pauses for human approval before "
        "high-impact actions (billing escalation, cancellation, password reset, "
        "...) via POST /runs/{run_id}/decision."
    )

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()
        # Checkpoints are intentionally process-local for this demo app. The
        # persisted pending RunResult lets ExecutionService resume safely after
        # a restart; successful resumes delete the in-memory thread below.
        self._checkpointer = InMemorySaver()
        self._graphs = {
            family: self._build_graph(module) for family, module in FAMILY_MODULES.items()
        }
        # run_id -> (family, registered_at), for runs awaiting resume(). Cleared
        # on resume() or once a run finishes without pausing; stale entries
        # (e.g. abandoned pending_approval runs) are swept by
        # `_evict_stale_runs` after PENDING_RUN_TTL.
        self._pending_runs: dict[str, tuple[ScenarioFamily, datetime]] = {}

    def _build_graph(self, module: Any):
        nodes = module.AgentNodes(self._client)
        graph = StateGraph(module.AgentState)
        graph.add_node("plan", nodes.plan)
        graph.add_node("act", nodes.act)
        graph.add_node("decide", nodes.decide)
        graph.add_node("approval", _make_approval(module))
        graph.add_node("finalize", nodes.finalize)
        graph.add_edge(START, "plan")
        graph.add_conditional_edges(
            "plan", nodes.route_after_plan, {"act": "act", "decide": "decide"}
        )
        graph.add_edge("act", "plan")
        graph.add_conditional_edges(
            "decide",
            _make_route_after_decide(module),
            {"approval": "approval", "finalize": "finalize"},
        )
        graph.add_edge("approval", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=self._checkpointer)

    def _evict_stale_runs(self) -> None:
        cutoff = datetime.now(UTC) - PENDING_RUN_TTL
        stale_ids = [
            run_id
            for run_id, (_, registered_at) in self._pending_runs.items()
            if registered_at < cutoff
        ]
        for run_id in stale_ids:
            self._forget_run(run_id)

    def _forget_run(self, run_id: str) -> None:
        self._pending_runs.pop(run_id, None)
        self._checkpointer.delete_thread(run_id)

    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput:
        self._evict_stale_runs()
        self._pending_runs[run_id] = (scenario.family, datetime.now(UTC))
        module = FAMILY_MODULES[scenario.family]
        config = {"configurable": {"thread_id": run_id}}
        initial_state = module.initial_state(
            scenario.input,
            required_fields=scenario.required_fields,
            confidence_threshold=(
                scenario.confidence_threshold
                if scenario.confidence_threshold is not None
                else DEFAULT_CONFIDENCE_THRESHOLD
            ),
        )
        result = await self._graphs[scenario.family].ainvoke(initial_state, config=config)
        output = self._to_output(result)
        if output.pending_approval is None:
            self._forget_run(run_id)
        return output

    async def resume(self, run_id: str, decision: str) -> RunnerOutput:
        self._evict_stale_runs()
        family, _ = self._pending_runs.get(run_id, ("customer_support", datetime.now(UTC)))
        config = {"configurable": {"thread_id": run_id}}
        result = await self._graphs[family].ainvoke(
            Command(resume={"decision": decision}), config=config
        )
        self._forget_run(run_id)
        return self._to_output(result)

    def _to_output(self, result: dict[str, Any]) -> RunnerOutput:
        common = {
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "estimated_cost_usd": result["estimated_cost_usd"],
            "retries": result["retries"],
        }

        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            return RunnerOutput(
                output=payload.get("output", {}),
                actions=[],
                confidence=payload.get("confidence"),
                pending_approval=PendingApproval(
                    action=payload.get("action") or "",
                    reason=payload.get("reason")
                    or "This action needs human approval before it can be taken.",
                    details=payload.get("details", {}),
                ),
                trace_events=result.get("node_events", []),
                **common,
            )

        final = result["final"]
        return RunnerOutput(
            output=final["output"],
            actions=final["actions"],
            confidence=final.get("confidence", 1.0),
            trace_events=result.get("node_events", []),
            **common,
        )
