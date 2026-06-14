"""Level 4: agent workflow — a LangGraph state machine that plans, calls a
tool when it needs more information, and loops until it can decide on a
next action.

Graph: plan -> (act -> plan)* -> decide -> finalize. `plan` offers the model
a `lookup_order` tool; if it asks to call it, `act` runs the lookup and the
result is fed back to `plan` (dynamic routing via a conditional edge). Once
the model stops requesting tools, `decide` produces the final structured
JSON answer."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.runners.base import BaseRunner
from app.runners.families import FAMILY_MODULES
from app.schemas.run import RunnerOutput
from app.schemas.scenario import Scenario
from app.services.checkpoint_policy import DEFAULT_CONFIDENCE_THRESHOLD
from app.services.llm_client import LLMClient


class AgentRunner(BaseRunner):
    name = "agent"
    level = 4
    description = (
        "LangGraph agent: plans, calls a lookup_order tool when needed, and "
        "loops (plan -> act -> plan) until it can decide on a next action."
    )

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()
        self._graphs = {
            family: self._build_graph(module) for family, module in FAMILY_MODULES.items()
        }

    def _build_graph(self, module: Any):
        nodes = module.AgentNodes(self._client)
        graph = StateGraph(module.AgentState)
        graph.add_node("plan", nodes.plan)
        graph.add_node("act", nodes.act)
        graph.add_node("decide", nodes.decide)
        graph.add_node("finalize", nodes.finalize)
        graph.add_edge(START, "plan")
        graph.add_conditional_edges(
            "plan", nodes.route_after_plan, {"act": "act", "decide": "decide"}
        )
        graph.add_edge("act", "plan")
        graph.add_edge("decide", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput:
        module = FAMILY_MODULES[scenario.family]
        initial_state = module.initial_state(
            scenario.input,
            required_fields=scenario.required_fields,
            confidence_threshold=(
                scenario.confidence_threshold
                if scenario.confidence_threshold is not None
                else DEFAULT_CONFIDENCE_THRESHOLD
            ),
        )
        result = await self._graphs[scenario.family].ainvoke(initial_state)
        final = result["final"]
        return RunnerOutput(
            output=final["output"],
            actions=final["actions"],
            confidence=final.get("confidence", 1.0),
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            estimated_cost_usd=result["estimated_cost_usd"],
            retries=result["retries"],
            trace_events=result.get("node_events", []),
        )
