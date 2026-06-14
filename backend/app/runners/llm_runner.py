"""Level 2: single LLM call with structured (JSON) output.

No tools, no planning, no retries beyond a single reattempt if the model's
reply doesn't parse."""

import logging

from app.runners import diff_review, hiring_screening, incident_triage
from app.runners.base import BaseRunner
from app.runners.json_retry import JsonAttempt, retry_valid_json
from app.runners.policy_qa import NO_RETRIEVAL_SYSTEM_PROMPT, parse_policy_proposal
from app.runners.triage import ALLOWED_ACTIONS, INTENT_LABELS
from app.schemas.run import RunnerOutput
from app.schemas.scenario import Scenario
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

ACTION_LINES = "\n".join(f"- {name}: {desc}" for name, desc in ALLOWED_ACTIONS.items())

SYSTEM_PROMPT = f"""You are a customer support triage assistant. Read the \
customer's message and reply with a single JSON object with these fields:

- "intent": one of {INTENT_LABELS}
- "order_id": the order number mentioned in the message, or null if none
- "customer_email": the customer's email address, or null if none
- "action": the single most appropriate next step, one of:
{ACTION_LINES}

Reply with ONLY the JSON object — no markdown, no commentary."""

MAX_ATTEMPTS = 2


class LLMRunner(BaseRunner):
    name = "llm"
    level = 2
    description = (
        "Single LLM call with structured JSON output. "
        "No tools, no planning."
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

        async def fetch() -> JsonAttempt:
            response = await self._client.complete_json(SYSTEM_PROMPT, scenario.input)
            return JsonAttempt(
                data=response.data,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                estimated_cost_usd=response.estimated_cost_usd,
            )

        def parse(data: dict) -> tuple[dict, list[str], str, str]:
            intent = str(data["intent"])
            action = str(data["action"])

            output: dict = {"intent": intent}
            if order_id := data.get("order_id"):
                output["order_id"] = str(order_id)
            if customer_email := data.get("customer_email"):
                output["customer_email"] = str(customer_email)

            actions = [action] if action in ALLOWED_ACTIONS else []
            return output, actions, intent, action

        result = await retry_valid_json(fetch, parse, attempts=MAX_ATTEMPTS)
        output, actions, intent, action = result.value

        logger.info(
            "llm runner intent=%s action=%s attempt=%d", intent, action, result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output=output,
            actions=actions,
            confidence=1.0,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_diff_review(self, scenario: Scenario) -> RunnerOutput:
        async def fetch() -> JsonAttempt:
            response = await self._client.complete_json(
                diff_review.NO_CONTEXT_SYSTEM_PROMPT, scenario.input
            )
            return JsonAttempt(
                data=response.data,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                estimated_cost_usd=response.estimated_cost_usd,
            )

        result = await retry_valid_json(
            fetch,
            diff_review.parse_diff_review_proposal,
            attempts=MAX_ATTEMPTS,
        )
        proposal = result.value

        logger.info(
            "llm diff review verdict=%s attempt=%d",
            proposal["output"]["verdict"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output=proposal["output"],
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_policy_qa(self, scenario: Scenario) -> RunnerOutput:
        async def fetch() -> JsonAttempt:
            response = await self._client.complete_json(NO_RETRIEVAL_SYSTEM_PROMPT, scenario.input)
            return JsonAttempt(
                data=response.data,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                estimated_cost_usd=response.estimated_cost_usd,
            )

        def parse(data: dict) -> dict:
            proposal = parse_policy_proposal(data, [])
            if not proposal["output"]["policy_id"]:
                raise KeyError("policy_id")
            return proposal

        result = await retry_valid_json(fetch, parse, attempts=MAX_ATTEMPTS)
        proposal = result.value

        logger.info(
            "llm policy qa policy_id=%s attempt=%d",
            proposal["output"]["policy_id"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output=proposal["output"],
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_incident_triage(self, scenario: Scenario) -> RunnerOutput:
        async def fetch() -> JsonAttempt:
            response = await self._client.complete_json(
                incident_triage.NO_CONTEXT_SYSTEM_PROMPT, scenario.input
            )
            return JsonAttempt(
                data=response.data,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                estimated_cost_usd=response.estimated_cost_usd,
            )

        result = await retry_valid_json(
            fetch,
            incident_triage.parse_incident_proposal,
            attempts=MAX_ATTEMPTS,
        )
        proposal = result.value

        logger.info(
            "llm incident category=%s attempt=%d",
            proposal["output"]["category"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output=proposal["output"],
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            retries=result.retries,
        )

    async def _execute_hiring_screening(self, scenario: Scenario) -> RunnerOutput:
        async def fetch() -> JsonAttempt:
            response = await self._client.complete_json(
                hiring_screening.NO_CONTEXT_SYSTEM_PROMPT, scenario.input
            )
            return JsonAttempt(
                data=response.data,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                estimated_cost_usd=response.estimated_cost_usd,
            )

        result = await retry_valid_json(
            fetch,
            hiring_screening.parse_screening_proposal,
            attempts=MAX_ATTEMPTS,
        )
        proposal = result.value

        logger.info(
            "llm hiring decision=%s attempt=%d",
            proposal["output"]["decision"],
            result.attempt,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output=proposal["output"],
            actions=proposal["actions"],
            confidence=1.0,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            retries=result.retries,
        )
