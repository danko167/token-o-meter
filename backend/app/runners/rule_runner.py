"""Level 0: deterministic rules — regex extraction and keyword matching.

This is the baseline every higher abstraction must beat. It is intentionally
simple: if it scores well on a scenario, nothing smarter is justified."""

import logging

from app.runners import diff_review
from app.runners.base import BaseRunner
from app.runners.hiring_screening import score_resume
from app.runners.incident_triage import classify_incident
from app.runners.policy_qa import extract_best_sentence
from app.runners.triage import INTENT_RULES, extract_entities
from app.schemas.run import RunnerOutput
from app.schemas.scenario import Scenario
from app.services.policy_docs import search_policy

logger = logging.getLogger(__name__)

class RuleRunner(BaseRunner):
    name = "rules"
    level = 0
    description = "Deterministic regex extraction and keyword decision table."

    async def execute(self, scenario: Scenario, run_id: str) -> RunnerOutput:
        if scenario.family == "git_diff_review":
            findings = diff_review.run_static_checks(scenario.input)
            verdict = diff_review.verdict_from_findings(findings)
            output = {"verdict": verdict, "findings": findings}
            logger.info(
                "rules diff verdict=%s findings=%d", verdict, len(findings),
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(output=output, confidence=1.0)

        if scenario.family == "policy_qa":
            matches = search_policy(scenario.input, top_k=1)
            if not matches:
                return RunnerOutput(output={"policy_id": None}, confidence=0.0)

            policy_id = matches[0]["policy_id"]
            output = {
                "policy_id": policy_id,
                "answer": extract_best_sentence(scenario.input, policy_id),
            }
            logger.info(
                "rules matched policy_id=%s", policy_id,
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(output=output, confidence=1.0)

        if scenario.family == "incident_triage":
            output = classify_incident(scenario.input)
            logger.info(
                "rules incident category=%s severity=%s",
                output["category"], output["severity"],
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(output=output, confidence=1.0)

        if scenario.family == "hiring_screening":
            output = score_resume(scenario.input)
            logger.info(
                "rules hiring decision=%s match_score=%s",
                output["decision"], output["match_score"],
                extra={"scenario_id": scenario.id},
            )
            return RunnerOutput(output=output, confidence=1.0)

        text = scenario.input.lower()

        intent = "unknown"
        matched_keyword = None
        for candidate, keywords in INTENT_RULES:
            for keyword in keywords:
                if keyword in text:
                    intent, matched_keyword = candidate, keyword
                    break
            if matched_keyword:
                break

        output: dict = {"intent": intent, **extract_entities(scenario.input)}

        logger.info(
            "rules matched intent=%s keyword=%r", intent, matched_keyword,
            extra={"scenario_id": scenario.id},
        )
        # Rules either match or they don't — confidence is binary.
        return RunnerOutput(output=output, confidence=1.0 if intent != "unknown" else 0.0)
