"""Evaluation engine: deterministic checks plus optional LLM-as-judge."""

import json

from app.schemas.run import Evaluation, EvaluationCheck, RunnerOutput
from app.schemas.scenario import Scenario
from app.services.llm_client import LLMClient


def evaluate(scenario: Scenario, result: RunnerOutput) -> Evaluation:
    checks: list[EvaluationCheck] = []

    for key, expected_value in scenario.expected.items():
        actual = result.output.get(key)
        checks.append(
            EvaluationCheck(
                name=f"expected.{key}",
                passed=actual == expected_value,
                detail=f"expected {expected_value!r}, got {actual!r}",
            )
        )

    for field in scenario.required_fields:
        present = result.output.get(field) not in (None, "", [])
        checks.append(
            EvaluationCheck(
                name=f"required_field.{field}",
                passed=present,
                detail="present" if present else "missing",
            )
        )

    for action in scenario.forbidden_actions:
        taken = action in result.actions
        checks.append(
            EvaluationCheck(
                name=f"forbidden_action.{action}",
                passed=not taken,
                detail="not taken" if not taken else "FORBIDDEN ACTION TAKEN",
            )
        )

    return _rescore(checks)


async def evaluate_with_judge(
    scenario: Scenario,
    result: RunnerOutput,
    judge_client: LLMClient | None = None,
) -> Evaluation:
    """Evaluate a result, using an LLM judge only for subjective families.

    The deterministic checks remain the baseline. If a judge is configured for
    Git Diff Review, its score is added as one more check so it influences the
    final 0-100 score without replacing explicit scenario constraints.
    """
    base = evaluate(scenario, result)
    if scenario.family != "git_diff_review" or judge_client is None:
        return base

    try:
        response = await judge_client.complete_json(
            JUDGE_SYSTEM_PROMPT,
            json.dumps(
                {
                    "scenario": {
                        "id": scenario.id,
                        "input": scenario.input,
                        "expected": scenario.expected,
                        "required_fields": scenario.required_fields,
                        "forbidden_actions": scenario.forbidden_actions,
                    },
                    "runner_output": result.output,
                    "actions": result.actions,
                },
                indent=2,
            ),
        )
        judge_score = int(response.data["score"])
        explanation = str(response.data.get("explanation") or "")
    except Exception as exc:
        checks = [
            *base.checks,
            EvaluationCheck(
                name="llm_judge.available",
                passed=False,
                detail=f"judge unavailable: {type(exc).__name__}: {exc}",
            ),
        ]
        return _rescore(checks)

    judge_score = max(0, min(100, judge_score))
    checks = [
        *base.checks,
        EvaluationCheck(
            name="llm_judge.quality",
            passed=judge_score >= 80,
            detail=f"score={judge_score}; {explanation}",
        ),
    ]
    return _rescore(checks)


def _rescore(checks: list[EvaluationCheck]) -> Evaluation:
    if not checks:
        return Evaluation(score=0, checks=[])
    score = round(100 * sum(check.passed for check in checks) / len(checks))
    return Evaluation(score=score, checks=checks)


JUDGE_SYSTEM_PROMPT = """You are an impartial code-review quality judge.
Evaluate whether the runner output is useful, grounded in the diff, and aligned
with the expected scenario constraints. Reply with ONLY JSON:
{
  "score": integer from 0 to 100,
  "explanation": "brief reason"
}

Use a high score when the verdict and findings are specific, correct, and
actionable. Penalize missing blockers, hallucinated findings, vague summaries,
or actions that conflict with the scenario."""
