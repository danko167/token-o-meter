"""Shared LangGraph plumbing for AgentRunner (Level 4) and
HumanCheckpointRunner (Level 5).

Both runners give the model a single tool (`lookup_order`) and let it loop:

    plan -> (act -> plan)* -> decide -> finalize

`plan` calls the LLM with the tool available; if it asks to call the tool,
`act` runs `lookup_order` and feeds the result back, looping to `plan` again.
Once the model stops requesting tools (or the iteration cap is hit), `decide`
asks for the final structured JSON answer. HumanCheckpointRunner inserts an
`approval` node between `decide` and `finalize` for actions that need a human
sign-off — see `human_checkpoint_runner.py`.
"""

import json
import logging
import time
from typing import Any, TypedDict

from app.runners.graph_helpers import message_preview, message_previews, node_event, truncate_value
from app.runners.triage import ALLOWED_ACTIONS, INTENT_LABELS
from app.schemas.run import TraceEvent
from app.services.checkpoint_policy import DEFAULT_CONFIDENCE_THRESHOLD, parse_confidence
from app.services.llm_client import LLMClient
from app.services.order_lookup import LOOKUP_ORDER_TOOL_SCHEMA, lookup_order

logger = logging.getLogger(__name__)

ACTION_LINES = "\n".join(f"- {name}: {desc}" for name, desc in ALLOWED_ACTIONS.items())

SYSTEM_PROMPT = f"""You are a customer support triage agent. You have access to a \
`lookup_order` tool that returns an order's status, tracking info, carrier, items, \
and how many times it was charged.

Work step by step:
1. Read the customer's message.
2. If it references an order ID, call lookup_order to check the order before deciding.
3. Once you have enough information, respond with ONLY a JSON object with these fields:
- "intent": one of {INTENT_LABELS}
- "order_id": the order number, or null
- "customer_email": the customer's email, or null
- "order_status": a short summary of the order lookup result, or null if you didn't \
look one up
- "action": the single most appropriate next step, one of:
{ACTION_LINES}
- "confidence": a number from 0.0 to 1.0 indicating how confident you are in this decision

Do not call lookup_order more than once for the same order ID."""

FINAL_ANSWER_PROMPT = "Now reply with ONLY the JSON object as specified."

#: Safety cap on plan/act loops before forcing a decision.
MAX_ITERATIONS = 3
#: Retries for the final structured-JSON decision step.
MAX_DECIDE_ATTEMPTS = 2

#: Actions with real-world consequences — HumanCheckpointRunner pauses for
#: approval before taking any of these.
RISKY_ACTIONS: set[str] = {
    "escalate_billing_review",
    "escalate_shipping_review",
    "escalate_general_review",
    "process_cancellation",
    "send_password_reset",
}


class AgentState(TypedDict):
    messages: list[dict[str, Any]]
    iterations: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    retries: int
    tool_calls_made: list[dict[str, Any]]
    proposed: dict[str, Any] | None
    approval_decision: str | None
    final: dict[str, Any] | None
    node_events: list[TraceEvent]
    required_fields: list[str]
    confidence_threshold: float


def initial_state(
    scenario_input: str,
    required_fields: list[str] | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> AgentState:
    return AgentState(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": scenario_input},
        ],
        iterations=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
        retries=0,
        tool_calls_made=[],
        proposed=None,
        approval_decision=None,
        final=None,
        node_events=[],
        required_fields=required_fields or [],
        confidence_threshold=confidence_threshold,
    )


class AgentNodes:
    """LangGraph node implementations bound to a single LLMClient."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def plan(self, state: AgentState) -> dict[str, Any]:
        start = time.perf_counter()
        response = await self._client.chat(state["messages"], tools=[LOOKUP_ORDER_TOOL_SCHEMA])
        message: dict[str, Any] = {"role": "assistant", "content": response.content}
        if response.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in response.tool_calls
            ]
        return {
            "messages": [*state["messages"], message],
            "iterations": state["iterations"] + 1,
            "prompt_tokens": state["prompt_tokens"] + response.prompt_tokens,
            "completion_tokens": state["completion_tokens"] + response.completion_tokens,
            "estimated_cost_usd": state["estimated_cost_usd"] + response.estimated_cost_usd,
            "node_events": [
                *state["node_events"],
                node_event(
                    "plan",
                    start,
                    response.prompt_tokens,
                    response.completion_tokens,
                    response.estimated_cost_usd,
                    {
                        "tool_calls": len(response.tool_calls),
                        "input_messages": message_previews(state["messages"]),
                        "assistant_message": message_preview(message),
                    },
                ),
            ],
        }

    def route_after_plan(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if last.get("tool_calls") and state["iterations"] < MAX_ITERATIONS:
            return "act"
        return "decide"

    async def act(self, state: AgentState) -> dict[str, Any]:
        start = time.perf_counter()
        last = state["messages"][-1]
        new_messages: list[dict[str, Any]] = []
        tool_calls_made = list(state["tool_calls_made"])

        for call in last.get("tool_calls", []):
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            order_id = str(args.get("order_id", ""))
            tool_start = time.perf_counter()
            order = lookup_order(order_id)
            duration_ms = round((time.perf_counter() - tool_start) * 1000, 1)
            tool_calls_made.append(
                {
                    "name": "lookup_order",
                    "order_id": order_id,
                    "found": order is not None,
                    "duration_ms": duration_ms,
                }
            )
            content = json.dumps(
                order if order is not None else {"error": f"No order found with id {order_id}"}
            )
            new_messages.append({"role": "tool", "tool_call_id": call["id"], "content": content})

        logger.info("agent graph called lookup_order: %s", tool_calls_made)
        return {
            "messages": [*state["messages"], *new_messages],
            "tool_calls_made": tool_calls_made,
            "node_events": [
                *state["node_events"],
                node_event(
                    "act",
                    start,
                    details={
                        "tool_calls": tool_calls_made,
                        "tool_messages": message_previews(new_messages),
                    },
                ),
            ],
        }

    async def decide(self, state: AgentState) -> dict[str, Any]:
        start = time.perf_counter()
        messages = [*state["messages"], {"role": "user", "content": FINAL_ANSWER_PROMPT}]
        prompt_tokens = state["prompt_tokens"]
        completion_tokens = state["completion_tokens"]
        estimated_cost_usd = state["estimated_cost_usd"]
        retries = state["retries"]

        for attempt in range(MAX_DECIDE_ATTEMPTS):
            response = await self._client.chat(messages, json_mode=True)
            prompt_tokens += response.prompt_tokens
            completion_tokens += response.completion_tokens
            estimated_cost_usd += response.estimated_cost_usd

            try:
                data = json.loads(response.content or "{}")
                intent = str(data["intent"])
                action = str(data["action"])
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                logger.warning("agent decide attempt %d produced bad JSON: %s", attempt + 1, exc)
                retries += 1
                continue

            output: dict[str, Any] = {"intent": intent}
            for key in ("order_id", "customer_email", "order_status"):
                if value := data.get(key):
                    output[key] = value
            if state["tool_calls_made"]:
                output["tool_calls"] = state["tool_calls_made"]

            actions = [action] if action in ALLOWED_ACTIONS else []
            confidence = parse_confidence(data.get("confidence"))
            assistant_message = {"role": "assistant", "content": response.content}
            return {
                "messages": [*state["messages"], assistant_message],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost_usd": estimated_cost_usd,
                "retries": retries,
                "proposed": {
                    "output": output,
                    "actions": actions,
                    "action": action,
                    "confidence": confidence,
                },
                "node_events": [
                    *state["node_events"],
                    node_event(
                        "decide",
                        start,
                        prompt_tokens - state["prompt_tokens"],
                        completion_tokens - state["completion_tokens"],
                        estimated_cost_usd - state["estimated_cost_usd"],
                        {
                            "attempt": attempt + 1,
                            "action": action,
                            "input_messages": message_previews(messages),
                            "assistant_message": message_preview(assistant_message),
                        },
                    ),
                ],
            }

        logger.warning(
            "agent decide exhausted %d attempts; falling back to review", MAX_DECIDE_ATTEMPTS
        )
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "retries": retries,
            "proposed": {
                "output": {"intent": "unknown"},
                "actions": ["escalate_general_review"],
                "action": "escalate_general_review",
                "confidence": 0.0,
            },
            "node_events": [
                *state["node_events"],
                node_event(
                    "decide",
                    start,
                    details={
                        "fallback": True,
                        "retries": retries,
                        "input_messages": message_previews(messages),
                    },
                ),
            ],
        }

    def finalize(self, state: AgentState) -> dict[str, Any]:
        start = time.perf_counter()
        proposed = state["proposed"] or {"output": {}, "actions": [], "action": None}
        output = dict(proposed["output"])
        actions = list(proposed["actions"])

        decision = state["approval_decision"]
        if decision is not None:
            output["approval_decision"] = decision
            if decision == "reject" and actions:
                output["proposed_action"] = actions[0]
                actions = ["escalate_general_review"]

        return {
            "final": {
                "output": output,
                "actions": actions,
                "confidence": proposed.get("confidence", 1.0),
            },
            "node_events": [
                *state["node_events"],
                node_event(
                    "finalize",
                    start,
                    details={"actions": actions, "output": truncate_value(output)},
                ),
            ],
        }
