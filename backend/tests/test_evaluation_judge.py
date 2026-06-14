import pytest

from app.schemas.run import RunnerOutput
from app.schemas.scenario import Scenario
from app.services.evaluation import evaluate_with_judge
from app.services.llm_client import LLMResponse

pytestmark = pytest.mark.anyio


class FakeJudgeClient:
    async def complete_json(self, system: str, user: str) -> LLMResponse:
        return LLMResponse(
            data={"score": 92, "explanation": "Specific and actionable review."},
            prompt_tokens=10,
            completion_tokens=5,
            estimated_cost_usd=0.0,
        )


async def test_git_diff_review_can_include_llm_judge_check():
    scenario = Scenario(
        id="diff",
        name="Diff",
        family="git_diff_review",
        input="diff --git a/app.py b/app.py",
        expected={"verdict": "request_changes"},
        required_fields=["findings"],
    )
    output = RunnerOutput(
        output={"verdict": "request_changes", "findings": [{"category": "security"}]},
        actions=["request_changes"],
    )

    evaluation = await evaluate_with_judge(scenario, output, FakeJudgeClient())

    assert any(check.name == "llm_judge.quality" for check in evaluation.checks)
    assert evaluation.score == 100


async def test_non_subjective_family_skips_llm_judge():
    scenario = Scenario(
        id="email",
        name="Email",
        family="customer_support",
        input="hello",
        expected={"intent": "billing_issue"},
    )
    output = RunnerOutput(output={"intent": "billing_issue"})

    evaluation = await evaluate_with_judge(scenario, output, FakeJudgeClient())

    assert [check.name for check in evaluation.checks] == ["expected.intent"]
