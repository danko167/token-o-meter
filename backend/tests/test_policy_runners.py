"""Policy QA coverage for all abstraction levels without network calls."""

import json

import pytest

from app.runners.agent_runner import AgentRunner
from app.runners.human_checkpoint_runner import HumanCheckpointRunner
from app.runners.llm_runner import LLMRunner
from app.runners.rule_runner import RuleRunner
from app.runners.tool_runner import ToolRunner
from app.runners.workflow_runner import WorkflowRunner
from app.schemas.scenario import Scenario
from app.services.llm_client import ChatResponse, LLMResponse, ToolCall
from tests.fakes import FakeChatClient
from tests.test_llm_runner import FakeLLMClient

pytestmark = pytest.mark.anyio


def make_policy_scenario(input_text: str | None = None) -> Scenario:
    return Scenario(
        id="policy-refund-window",
        name="Policy QA - Refund Window",
        family="policy_qa",
        input=input_text
        or "A customer says their item arrived 18 days ago and it is defective.",
    )


async def test_rule_runner_answers_from_policy_search():
    result = await RuleRunner().execute(make_policy_scenario(), "run-policy-rules")

    assert result.output["policy_id"] == "refund-policy"
    assert "30 days" in result.output["answer"]
    assert result.actions == []


async def test_workflow_runner_classifies_and_answers_policy_question():
    result = await WorkflowRunner().execute(make_policy_scenario(), "run-policy-workflow")

    assert result.output["category"] == "refunds"
    assert result.output["policy_id"] == "refund-policy"
    assert result.actions == ["provide_policy_answer"]


async def test_llm_runner_policy_qa_uses_policy_parser():
    client = FakeLLMClient(
        [
            LLMResponse(
                data={
                    "category": "refunds",
                    "policy_id": "refund-policy",
                    "answer": "Yes, defective items are inside the 30-day refund window.",
                    "citations": ["refund-policy"],
                    "action": "provide_policy_answer",
                },
                prompt_tokens=50,
                completion_tokens=20,
                estimated_cost_usd=0.00001,
            )
        ]
    )
    result = await LLMRunner(client=client).execute(make_policy_scenario(), "run-policy-llm")

    assert result.output["policy_id"] == "refund-policy"
    assert result.actions == ["provide_policy_answer"]
    assert client.calls == 1


async def test_tool_runner_policy_qa_calls_search_policy_then_answers():
    client = FakeChatClient(
        [
            ChatResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="search_policy",
                        arguments='{"query": "defective item refund 18 days", "top_k": 2}',
                    )
                ],
                prompt_tokens=60,
                completion_tokens=10,
                estimated_cost_usd=0.00001,
            ),
            ChatResponse(
                content=json.dumps(
                    {
                        "category": "refunds",
                        "policy_id": "refund-policy",
                        "answer": "Yes. Defective items can be refunded within 30 days.",
                        "citations": ["refund-policy"],
                        "action": "provide_policy_answer",
                    }
                ),
                tool_calls=[],
                prompt_tokens=80,
                completion_tokens=30,
                estimated_cost_usd=0.00002,
            ),
        ]
    )

    result = await ToolRunner(client=client).execute(make_policy_scenario(), "run-policy-tool")

    assert result.output["policy_id"] == "refund-policy"
    assert result.output["tool_calls"][0]["name"] == "search_policy"
    assert result.actions == ["provide_policy_answer"]
    assert client.calls == 2


async def test_agent_runner_policy_qa_loops_through_search_tool():
    client = FakeChatClient(_policy_agent_responses())

    result = await AgentRunner(client=client).execute(make_policy_scenario(), "run-policy-agent")

    assert result.output["policy_id"] == "refund-policy"
    assert result.output["tool_calls"][0]["name"] == "search_policy"
    assert result.actions == ["provide_policy_answer"]
    assert client.calls == 3


async def test_human_checkpoint_policy_qa_pauses_and_resumes():
    client = FakeChatClient(_policy_agent_responses())
    runner = HumanCheckpointRunner(client=client)

    pending = await runner.execute(make_policy_scenario(), "run-policy-human")

    assert pending.actions == []
    assert pending.pending_approval is not None
    assert pending.pending_approval.action == "provide_policy_answer"

    result = await runner.resume("run-policy-human", "approve")

    assert result.pending_approval is None
    assert result.actions == ["provide_policy_answer"]
    assert result.output["approval_decision"] == "approve"


def _policy_agent_responses() -> list[ChatResponse]:
    return [
        ChatResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="search_policy",
                    arguments='{"query": "defective item refund 18 days", "top_k": 2}',
                )
            ],
            prompt_tokens=60,
            completion_tokens=10,
            estimated_cost_usd=0.00001,
        ),
        ChatResponse(
            content="",
            tool_calls=[],
            prompt_tokens=70,
            completion_tokens=10,
            estimated_cost_usd=0.00001,
        ),
        ChatResponse(
            content=json.dumps(
                {
                    "category": "refunds",
                    "policy_id": "refund-policy",
                    "answer": "Yes. Defective items can be refunded within 30 days.",
                    "citations": ["refund-policy"],
                    "action": "provide_policy_answer",
                }
            ),
            tool_calls=[],
            prompt_tokens=80,
            completion_tokens=30,
            estimated_cost_usd=0.00002,
        ),
    ]
