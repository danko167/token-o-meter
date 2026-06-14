"""Level 3: LLM with tool access (retrieval, API calls, DB lookups).

A single conversation with the configured LLM: the model is offered a `lookup_order`
tool and may call it once before answering. Unlike AgentRunner (Level 4),
there's no planning loop or dynamic routing — at most one tool round trip,
then a final structured-JSON answer."""

import json
import logging
import time

import app.runners.policy_qa as policy_qa
from app.runners import diff_review, hiring_screening, incident_triage
from app.runners.base import BaseRunner
from app.runners.json_retry import JsonAttempt, chat_json_fetch, retry_valid_json
from app.runners.triage import ALLOWED_ACTIONS, INTENT_LABELS
from app.schemas.run import RunnerOutput
from app.schemas.scenario import Scenario
from app.services.llm_client import LLMClient, ToolCall
from app.services.order_lookup import LOOKUP_ORDER_TOOL_SCHEMA, lookup_order
from app.services.policy_docs import SEARCH_POLICY_TOOL_SCHEMA, search_policy
from app.services.repo_files import READ_FILE_TOOL_SCHEMA, read_file
from app.services.role_requirements import (
    LOOKUP_ROLE_REQUIREMENTS_TOOL_SCHEMA,
    lookup_role_requirements,
)
from app.services.service_status import CHECK_SERVICE_STATUS_TOOL_SCHEMA, check_service_status

logger = logging.getLogger(__name__)

ACTION_LINES = "\n".join(f"- {name}: {desc}" for name, desc in ALLOWED_ACTIONS.items())

SYSTEM_PROMPT = f"""You are a customer support triage assistant with access to a \
`lookup_order` tool that returns an order's status, tracking info, carrier, items, \
and how many times it was charged.

If the customer's message references an order ID, call lookup_order to check the \
order before deciding on an action. Then reply with ONLY a JSON object with these \
fields:

- "intent": one of {INTENT_LABELS}
- "order_id": the order number mentioned in the message, or null if none
- "customer_email": the customer's email address, or null if none
- "order_status": a short summary of the order lookup result, or null if you didn't \
look one up
- "action": the single most appropriate next step, one of:
{ACTION_LINES}

Reply with ONLY the JSON object — no markdown, no commentary."""

FINAL_ANSWER_PROMPT = "Now reply with ONLY the JSON object as specified."

MAX_ATTEMPTS = 2


def _append_tool_call_message(
    messages: list[dict], content: str, tool_calls: list[ToolCall]
) -> None:
    messages.append(
        {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in tool_calls
            ],
        }
    )


class ToolRunner(BaseRunner):
    name = "tool"
    level = 3
    description = (
        "Single LLM call with access to a lookup_order "
        "tool - at most one tool round trip before a structured JSON answer."
    )

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()

    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput:
        if scenario.family == "policy_qa":
            return await self._execute_policy_qa(scenario)
        if scenario.family == "git_diff_review":
            return await self._execute_diff_review(scenario)
        if scenario.family == "incident_triage":
            return await self._execute_incident_triage(scenario)
        if scenario.family == "hiring_screening":
            return await self._execute_hiring_screening(scenario)

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": scenario.input},
        ]
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = 0.0
        tool_calls_made: list[dict] = []

        first = await self._client.chat(messages, tools=[LOOKUP_ORDER_TOOL_SCHEMA])
        prompt_tokens += first.prompt_tokens
        completion_tokens += first.completion_tokens
        estimated_cost_usd += first.estimated_cost_usd

        if first.tool_calls:
            _append_tool_call_message(messages, first.content, first.tool_calls)
            for tc in first.tool_calls:
                try:
                    args = json.loads(tc.arguments or "{}")
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
                    order
                    if order is not None
                    else {"error": f"No order found with id {order_id}"}
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            logger.info(
                "tool runner called lookup_order: %s", tool_calls_made,
                extra={"scenario_id": scenario.id},
            )

        messages.append({"role": "user", "content": FINAL_ANSWER_PROMPT})

        async def fetch() -> JsonAttempt:
            return await chat_json_fetch(self._client, messages)

        def parse(data: dict) -> tuple[dict, list[str], str, str]:
            intent = str(data["intent"])
            action = str(data["action"])

            output: dict = {"intent": intent}
            for key in ("order_id", "customer_email", "order_status"):
                if value := data.get(key):
                    output[key] = value
            if tool_calls_made:
                output["tool_calls"] = tool_calls_made

            actions = [action] if action in ALLOWED_ACTIONS else []
            return output, actions, intent, action

        result = await retry_valid_json(fetch, parse, attempts=MAX_ATTEMPTS)
        output, actions, intent, action = result.value

        logger.info(
            "tool runner intent=%s action=%s attempt=%d", intent, action, result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output=output,
            actions=actions,
            confidence=1.0,
            prompt_tokens=prompt_tokens + result.prompt_tokens,
            completion_tokens=completion_tokens + result.completion_tokens,
            estimated_cost_usd=estimated_cost_usd + result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_policy_qa(self, scenario: Scenario) -> RunnerOutput:
        messages: list[dict] = [
            {"role": "system", "content": policy_qa.SYSTEM_PROMPT},
            {"role": "user", "content": scenario.input},
        ]
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = 0.0
        tool_calls_made: list[dict] = []
        retrieved: list[dict] = []

        first = await self._client.chat(messages, tools=[SEARCH_POLICY_TOOL_SCHEMA])
        prompt_tokens += first.prompt_tokens
        completion_tokens += first.completion_tokens
        estimated_cost_usd += first.estimated_cost_usd

        if first.tool_calls:
            _append_tool_call_message(messages, first.content, first.tool_calls)
            for tc in first.tool_calls:
                try:
                    args = json.loads(tc.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                query = str(args.get("query") or scenario.input)
                top_k = int(args.get("top_k") or 2)
                tool_start = time.perf_counter()
                matches = search_policy(query, top_k=top_k)
                duration_ms = round((time.perf_counter() - tool_start) * 1000, 1)
                retrieved.extend(matches)
                tool_calls_made.append(
                    {
                        "name": "search_policy",
                        "query": query,
                        "result_count": len(matches),
                        "duration_ms": duration_ms,
                    }
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(matches)}
                )

        messages.append({"role": "user", "content": policy_qa.FINAL_ANSWER_PROMPT})

        async def fetch() -> JsonAttempt:
            return await chat_json_fetch(self._client, messages)

        def parse(data: dict) -> dict:
            proposal = policy_qa.parse_policy_proposal(data, retrieved)
            if not proposal["output"]["policy_id"]:
                raise KeyError("policy_id")
            return proposal

        result = await retry_valid_json(fetch, parse, attempts=MAX_ATTEMPTS)
        proposal = result.value

        output = dict(proposal["output"])
        if tool_calls_made:
            output["tool_calls"] = tool_calls_made

        logger.info(
            "tool policy qa policy_id=%s attempt=%d",
            output["policy_id"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output=output,
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=prompt_tokens + result.prompt_tokens,
            completion_tokens=completion_tokens + result.completion_tokens,
            estimated_cost_usd=estimated_cost_usd + result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_diff_review(self, scenario: Scenario) -> RunnerOutput:
        messages: list[dict] = [
            {"role": "system", "content": diff_review.SYSTEM_PROMPT},
            {"role": "user", "content": scenario.input},
        ]
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = 0.0
        files_read: list[str] = []
        tool_calls_made: list[dict] = []

        first = await self._client.chat(messages, tools=[READ_FILE_TOOL_SCHEMA])
        prompt_tokens += first.prompt_tokens
        completion_tokens += first.completion_tokens
        estimated_cost_usd += first.estimated_cost_usd

        if first.tool_calls:
            _append_tool_call_message(messages, first.content, first.tool_calls)
            for tc in first.tool_calls:
                try:
                    args = json.loads(tc.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                path = str(args.get("path", ""))
                tool_start = time.perf_counter()
                content = read_file(path)
                duration_ms = round((time.perf_counter() - tool_start) * 1000, 1)
                if content is not None:
                    files_read.append(path)
                tool_calls_made.append(
                    {
                        "name": "read_file",
                        "path": path,
                        "found": content is not None,
                        "duration_ms": duration_ms,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": content if content is not None else f"File not found: {path}",
                    }
                )
            logger.info(
                "tool runner read files: %s", files_read,
                extra={"scenario_id": scenario.id},
            )

        messages.append({"role": "user", "content": diff_review.FINAL_ANSWER_PROMPT})

        async def fetch() -> JsonAttempt:
            return await chat_json_fetch(self._client, messages)

        result = await retry_valid_json(
            fetch,
            lambda data: diff_review.parse_diff_review_proposal(data, files_read),
            attempts=MAX_ATTEMPTS,
        )
        proposal = result.value

        logger.info(
            "tool diff review verdict=%s attempt=%d",
            proposal["output"]["verdict"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output={
                **proposal["output"],
                **({"tool_calls": tool_calls_made} if tool_calls_made else {}),
            },
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=prompt_tokens + result.prompt_tokens,
            completion_tokens=completion_tokens + result.completion_tokens,
            estimated_cost_usd=estimated_cost_usd + result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_incident_triage(self, scenario: Scenario) -> RunnerOutput:
        messages: list[dict] = [
            {"role": "system", "content": incident_triage.SYSTEM_PROMPT},
            {"role": "user", "content": scenario.input},
        ]
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = 0.0
        tool_calls_made: list[dict] = []
        service_status: dict | None = None

        first = await self._client.chat(messages, tools=[CHECK_SERVICE_STATUS_TOOL_SCHEMA])
        prompt_tokens += first.prompt_tokens
        completion_tokens += first.completion_tokens
        estimated_cost_usd += first.estimated_cost_usd

        if first.tool_calls:
            _append_tool_call_message(messages, first.content, first.tool_calls)
            for tc in first.tool_calls:
                try:
                    args = json.loads(tc.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                service = str(args.get("service", ""))
                tool_start = time.perf_counter()
                status = check_service_status(service)
                duration_ms = round((time.perf_counter() - tool_start) * 1000, 1)
                if status is not None:
                    service_status = status
                tool_calls_made.append(
                    {
                        "name": "check_service_status",
                        "service": service,
                        "found": status is not None,
                        "duration_ms": duration_ms,
                    }
                )
                content = json.dumps(
                    status
                    if status is not None
                    else {"error": f"No status found for service {service}"}
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            logger.info(
                "tool runner called check_service_status: %s", tool_calls_made,
                extra={"scenario_id": scenario.id},
            )

        messages.append({"role": "user", "content": incident_triage.FINAL_ANSWER_PROMPT})

        async def fetch() -> JsonAttempt:
            return await chat_json_fetch(self._client, messages)

        result = await retry_valid_json(
            fetch,
            lambda data: incident_triage.parse_incident_proposal(data, service_status),
            attempts=MAX_ATTEMPTS,
        )
        proposal = result.value

        logger.info(
            "tool incident category=%s attempt=%d",
            proposal["output"]["category"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output={
                **proposal["output"],
                **({"tool_calls": tool_calls_made} if tool_calls_made else {}),
            },
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=prompt_tokens + result.prompt_tokens,
            completion_tokens=completion_tokens + result.completion_tokens,
            estimated_cost_usd=estimated_cost_usd + result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_hiring_screening(self, scenario: Scenario) -> RunnerOutput:
        messages: list[dict] = [
            {"role": "system", "content": hiring_screening.SYSTEM_PROMPT},
            {"role": "user", "content": scenario.input},
        ]
        prompt_tokens = 0
        completion_tokens = 0
        estimated_cost_usd = 0.0
        tool_calls_made: list[dict] = []
        role: dict | None = None

        first = await self._client.chat(messages, tools=[LOOKUP_ROLE_REQUIREMENTS_TOOL_SCHEMA])
        prompt_tokens += first.prompt_tokens
        completion_tokens += first.completion_tokens
        estimated_cost_usd += first.estimated_cost_usd

        if first.tool_calls:
            _append_tool_call_message(messages, first.content, first.tool_calls)
            for tc in first.tool_calls:
                try:
                    args = json.loads(tc.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                role_id = str(args.get("role_id", ""))
                tool_start = time.perf_counter()
                looked_up = lookup_role_requirements(role_id)
                duration_ms = round((time.perf_counter() - tool_start) * 1000, 1)
                if looked_up is not None:
                    role = looked_up
                tool_calls_made.append(
                    {
                        "name": "lookup_role_requirements",
                        "role_id": role_id,
                        "found": looked_up is not None,
                        "duration_ms": duration_ms,
                    }
                )
                content = json.dumps(
                    looked_up
                    if looked_up is not None
                    else {"error": f"No role found with id {role_id}"}
                )
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": content})
            logger.info(
                "tool runner called lookup_role_requirements: %s", tool_calls_made,
                extra={"scenario_id": scenario.id},
            )

        messages.append({"role": "user", "content": hiring_screening.FINAL_ANSWER_PROMPT})

        async def fetch() -> JsonAttempt:
            return await chat_json_fetch(self._client, messages)

        result = await retry_valid_json(
            fetch,
            lambda data: hiring_screening.parse_screening_proposal(data, role),
            attempts=MAX_ATTEMPTS,
        )
        proposal = result.value

        logger.info(
            "tool hiring decision=%s attempt=%d",
            proposal["output"]["decision"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output={
                **proposal["output"],
                **({"tool_calls": tool_calls_made} if tool_calls_made else {}),
            },
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=prompt_tokens + result.prompt_tokens,
            completion_tokens=completion_tokens + result.completion_tokens,
            estimated_cost_usd=estimated_cost_usd + result.estimated_cost_usd,
            retries=result.retries,
        )
