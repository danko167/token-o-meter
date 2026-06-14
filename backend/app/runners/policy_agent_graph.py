"""LangGraph nodes for Policy QA agent and human-checkpoint runners."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import app.runners.policy_qa as policy_qa
from app.runners.agent_graph import AgentState
from app.runners.graph_helpers import message_preview, message_previews, node_event, truncate_value
from app.services.checkpoint_policy import DEFAULT_CONFIDENCE_THRESHOLD
from app.services.llm_client import LLMClient
from app.services.policy_docs import SEARCH_POLICY_TOOL_SCHEMA, search_policy

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3
MAX_DECIDE_ATTEMPTS = 2

#: Actions with real-world consequences — HumanCheckpointRunner pauses for
#: approval before taking any of these.
RISKY_ACTIONS: set[str] = {policy_qa.ACTION_NAME}


def initial_state(
    scenario_input: str,
    required_fields: list[str] | None = None,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> AgentState:
    return AgentState(
        messages=[
            {"role": "system", "content": policy_qa.SYSTEM_PROMPT},
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
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def plan(self, state: AgentState) -> dict[str, Any]:
        start = time.perf_counter()
        response = await self._client.chat(state["messages"], tools=[SEARCH_POLICY_TOOL_SCHEMA])
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
            query = str(args.get("query") or "")
            top_k = int(args.get("top_k") or 2)
            tool_start = time.perf_counter()
            matches = search_policy(query, top_k=top_k)
            duration_ms = round((time.perf_counter() - tool_start) * 1000, 1)
            tool_calls_made.append(
                {
                    "name": "search_policy",
                    "query": query,
                    "result_count": len(matches),
                    "duration_ms": duration_ms,
                }
            )
            new_messages.append(
                {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(matches)}
            )

        logger.info("policy agent graph called search_policy: %s", tool_calls_made)
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
        messages = [*state["messages"], {"role": "user", "content": policy_qa.FINAL_ANSWER_PROMPT}]
        prompt_tokens = state["prompt_tokens"]
        completion_tokens = state["completion_tokens"]
        estimated_cost_usd = state["estimated_cost_usd"]
        retries = state["retries"]
        retrieved = _retrieved_from_messages(state["messages"])

        for attempt in range(MAX_DECIDE_ATTEMPTS):
            response = await self._client.chat(messages, json_mode=True)
            prompt_tokens += response.prompt_tokens
            completion_tokens += response.completion_tokens
            estimated_cost_usd += response.estimated_cost_usd

            try:
                data = json.loads(response.content or "{}")
                proposed = policy_qa.parse_policy_proposal(data, retrieved)
                if not proposed["output"]["policy_id"]:
                    raise KeyError("policy_id")
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                logger.warning(
                    "policy agent decide attempt %d produced bad JSON: %s", attempt + 1, exc
                )
                retries += 1
                continue

            output = dict(proposed["output"])
            if state["tool_calls_made"]:
                output["tool_calls"] = state["tool_calls_made"]
            proposed["output"] = output
            assistant_message = {"role": "assistant", "content": response.content}

            return {
                "messages": [
                    *state["messages"],
                    assistant_message,
                ],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "estimated_cost_usd": estimated_cost_usd,
                "retries": retries,
                "proposed": proposed,
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
                            "action": proposed["action"],
                            "input_messages": message_previews(messages),
                            "assistant_message": message_preview(assistant_message),
                        },
                    ),
                ],
            }

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "retries": retries,
            "proposed": policy_qa.FALLBACK_PROPOSAL,
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
                actions = [policy_qa.REJECT_ACTION]

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


def _retrieved_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    retrieved: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        try:
            payload = json.loads(str(message.get("content") or "[]"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            retrieved.extend(item for item in payload if isinstance(item, dict))
    return retrieved
