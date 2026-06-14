"""Level 1: traditional automation — an explicit state machine with hard-
coded business rules. No ML/LLM involved; this is what a pre-AI engineering
team would ship: extract entities, classify intent, then apply policy."""

import logging

from app.runners import diff_review
from app.runners.base import BaseRunner
from app.runners.hiring_screening import score_resume
from app.runners.incident_triage import CATEGORY_TO_ACTION, classify_incident
from app.runners.policy_qa import (
    ACTION_NAME,
    POLICY_ID_BY_CATEGORY,
    classify_category,
    extract_best_sentence,
)
from app.runners.triage import INTENT_RULES, extract_entities
from app.schemas.run import RunnerOutput
from app.schemas.scenario import Scenario

logger = logging.getLogger(__name__)

# Policy table mapping each intent to a next action. Some intents branch on
# whether an order id was found — e.g. a billing dispute can't be escalated
# for review without one, and policy never allows an automatic refund.
ACTION_TABLE: dict[str, dict[str, str]] = {
    "billing_issue": {
        "with_order_id": "escalate_billing_review",
        "without_order_id": "request_order_id",
    },
    "shipping_issue": {
        "with_order_id": "provide_tracking_update",
        "without_order_id": "request_order_id",
    },
    "account_issue": {"default": "send_password_reset"},
    "cancellation": {"default": "process_cancellation"},
    "product_question": {"default": "answer_product_question"},
    "unknown": {"default": "escalate_general_review"},
}


class WorkflowRunner(BaseRunner):
    name = "workflow"
    level = 1
    description = (
        "Explicit state machine: extract entities, classify intent by keyword, "
        "then apply a policy table to pick the next action."
    )

    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput:
        if scenario.family == "git_diff_review":
            findings = diff_review.run_static_checks(scenario.input)
            verdict = diff_review.verdict_from_findings(findings)
            category = diff_review.classify_category(findings)
            output = {"category": category, "verdict": verdict, "findings": findings}
            logger.info(
                "workflow diff category=%s verdict=%s", category, verdict,
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(
                output=output,
                actions=[diff_review.VERDICT_TO_ACTION[verdict]],
                confidence=1.0,
            )

        if scenario.family == "policy_qa":
            category = classify_category(scenario.input)
            policy_id = POLICY_ID_BY_CATEGORY.get(category)
            output = {
                "category": category,
                "policy_id": policy_id,
                "answer": extract_best_sentence(scenario.input, policy_id),
            }
            logger.info(
                "workflow policy category=%s policy_id=%s", category, policy_id,
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(
                output=output,
                actions=[ACTION_NAME],
                confidence=1.0 if policy_id else 0.5,
            )

        if scenario.family == "incident_triage":
            output = classify_incident(scenario.input)
            action = CATEGORY_TO_ACTION[output["category"]]
            logger.info(
                "workflow incident category=%s action=%s", output["category"], action,
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(output=output, actions=[action], confidence=1.0)

        if scenario.family == "hiring_screening":
            output = score_resume(scenario.input)
            logger.info(
                "workflow hiring decision=%s", output["decision"],
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(output=output, actions=[output["decision"]], confidence=1.0)

        # State 1: extract entities
        entities = extract_entities(scenario.input)

        # State 2: classify intent
        text = scenario.input.lower()
        intent = "unknown"
        for candidate, keywords in INTENT_RULES:
            if any(keyword in text for keyword in keywords):
                intent = candidate
                break

        # State 3: apply policy to pick the next action
        rules = ACTION_TABLE[intent]
        if "default" in rules:
            action = rules["default"]
        elif "order_id" in entities:
            action = rules["with_order_id"]
        else:
            action = rules["without_order_id"]

        logger.info(
            "workflow intent=%s action=%s", intent, action,
            extra={"scenario_id": scenario.id},
        )
        return RunnerOutput(
            output={"intent": intent, **entities},
            actions=[action],
            confidence=1.0 if intent != "unknown" else 0.5,
        )
