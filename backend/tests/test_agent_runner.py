"""Unit tests for AgentRunner's LangGraph plan/act/decide loop against a fake
chat client — no network calls."""

import json

import pytest

from app.runners.agent_runner import AgentRunner
from app.schemas.scenario import Scenario
from app.services.llm_client import ChatResponse, ToolCall
from tests.fakes import FakeChatClient

pytestmark = pytest.mark.anyio


def make_scenario(input_text: str) -> Scenario:
    return Scenario(id="test-scenario", name="Test scenario", input=input_text)


MISSING_TEST_DIFF = """\
diff --git a/app/payments.py b/app/payments.py
index 1a2b3c4..5d6e7f8 100644
--- a/app/payments.py
+++ b/app/payments.py
@@ -1,2 +1,6 @@
 def calculate_total(price: float, quantity: int) -> float:
     return price * quantity
+
+
+def apply_discount(price: float, percent: float) -> float:
+    return price * (1 - percent / 100)
"""


def make_missing_test_diff_scenario() -> Scenario:
    return Scenario(
        id="diff-missing-test-coverage",
        name="Git Diff Review - Missing Test Coverage",
        family="git_diff_review",
        input=MISSING_TEST_DIFF,
    )


def make_policy_scenario(input_text: str) -> Scenario:
    return Scenario(
        id="policy-secret-trace",
        name="Policy QA - Secret Trace",
        family="policy_qa",
        input=input_text,
    )


async def test_agent_runner_loops_through_tool_call():
    client = FakeChatClient(
        [
            ChatResponse(
                content="",
                tool_calls=[
                    ToolCall(id="call_1", name="lookup_order", arguments='{"order_id": "1234"}')
                ],
                prompt_tokens=100,
                completion_tokens=20,
                estimated_cost_usd=0.0001,
            ),
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=120, completion_tokens=10,
                estimated_cost_usd=0.0001,
            ),
            ChatResponse(
                content=json.dumps(
                    {
                        "intent": "billing_issue",
                        "order_id": "1234",
                        "customer_email": "jane.doe@example.com",
                        "order_status": "delivered, charged twice",
                        "action": "escalate_billing_review",
                    }
                ),
                tool_calls=[],
                prompt_tokens=150,
                completion_tokens=40,
                estimated_cost_usd=0.0002,
            ),
        ]
    )
    runner = AgentRunner(client=client)

    result = await runner.execute(
        make_scenario("I was charged twice for order #1234. jane.doe@example.com"), "run-1"
    )

    assert result.output["intent"] == "billing_issue"
    assert result.output["tool_calls"][0]["name"] == "lookup_order"
    assert result.output["tool_calls"][0]["order_id"] == "1234"
    assert result.output["tool_calls"][0]["found"] is True
    assert result.output["tool_calls"][0]["duration_ms"] >= 0
    assert result.actions == ["escalate_billing_review"]
    assert result.prompt_tokens == 370
    assert result.completion_tokens == 70
    assert result.retries == 0
    assert client.calls == 3
    plan_event = next(event for event in result.trace_events if event.details["node"] == "plan")
    decide_event = next(event for event in result.trace_events if event.details["node"] == "decide")
    assert plan_event.details["input_messages"][-1]["role"] == "user"
    assert plan_event.details["assistant_message"]["tool_calls"][0]["name"] == "lookup_order"
    assert decide_event.details["assistant_message"]["content"].startswith('{"intent"')


async def test_agent_runner_finalizes_without_tool_call():
    client = FakeChatClient(
        [
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=80, completion_tokens=10,
                estimated_cost_usd=0.00005,
            ),
            ChatResponse(
                content=json.dumps({"intent": "shipping_issue", "action": "request_order_id"}),
                tool_calls=[],
                prompt_tokens=90,
                completion_tokens=15,
                estimated_cost_usd=0.00006,
            ),
        ]
    )
    runner = AgentRunner(client=client)

    result = await runner.execute(make_scenario("Where is my package?"), "run-2")

    assert result.output == {"intent": "shipping_issue"}
    assert result.actions == ["request_order_id"]
    assert client.calls == 2


async def test_agent_runner_caps_iterations_and_falls_back():
    """Model keeps requesting tool calls -> hits MAX_ITERATIONS, then `decide`
    gets unparseable JSON twice -> falls back to escalate_general_review."""
    tool_call = ToolCall(id="call_x", name="lookup_order", arguments='{"order_id": "9999"}')
    looping_response = ChatResponse(
        content="", tool_calls=[tool_call], prompt_tokens=10, completion_tokens=5,
        estimated_cost_usd=0.0,
    )
    bad_json_response = ChatResponse(
        content="nope", tool_calls=[], prompt_tokens=10, completion_tokens=5,
        estimated_cost_usd=0.0,
    )
    client = FakeChatClient([looping_response] * 3 + [bad_json_response] * 2)
    runner = AgentRunner(client=client)

    result = await runner.execute(make_scenario("???"), "run-3")

    assert result.output == {"intent": "unknown"}
    assert result.actions == ["escalate_general_review"]
    assert result.retries == 2
    assert client.calls == 5


async def test_agent_runner_diff_review_loops_through_read_file_tool():
    client = FakeChatClient(
        [
            ChatResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        name="read_file",
                        arguments='{"path": "tests/test_payments.py"}',
                    )
                ],
                prompt_tokens=80,
                completion_tokens=15,
                estimated_cost_usd=0.00001,
            ),
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=90, completion_tokens=10,
                estimated_cost_usd=0.00001,
            ),
            ChatResponse(
                content=json.dumps(
                    {
                        "verdict": "comment",
                        "findings": [
                            {
                                "category": "missing_tests",
                                "severity": "warning",
                                "message": "apply_discount has no test coverage.",
                            }
                        ],
                        "summary": "New function apply_discount is untested.",
                        "action": "comment_on_pr",
                    }
                ),
                tool_calls=[],
                prompt_tokens=120,
                completion_tokens=40,
                estimated_cost_usd=0.00002,
            ),
        ]
    )

    result = await AgentRunner(client=client).execute(
        make_missing_test_diff_scenario(), "run-diff-agent"
    )

    assert result.output["verdict"] == "comment"
    assert result.output["files_read"] == ["tests/test_payments.py"]
    assert result.actions == ["comment_on_pr"]
    assert client.calls == 3


async def test_agent_runner_diff_review_redacts_finalize_trace_output():
    leaked_secret = "sk-live-abcdef1234567890"
    client = FakeChatClient(
        [
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
                        "verdict": "request_changes",
                        "findings": [
                            {
                                "category": "hardcoded_secret",
                                "severity": "blocker",
                                "message": f"Hardcoded api_key={leaked_secret} found",
                            }
                        ],
                        "summary": "This diff hardcodes an API key.",
                        "action": "request_changes",
                    }
                ),
                tool_calls=[],
                prompt_tokens=100,
                completion_tokens=30,
                estimated_cost_usd=0.00002,
            ),
        ]
    )

    result = await AgentRunner(client=client).execute(
        make_missing_test_diff_scenario(), "run-diff-redact"
    )

    finalize_event = next(event for event in result.trace_events if event.details["node"] == "finalize")
    assert leaked_secret in result.output["findings"][0]["message"]
    assert leaked_secret not in json.dumps(finalize_event.details)
    assert "[redacted]" in json.dumps(finalize_event.details)


async def test_agent_runner_policy_qa_redacts_finalize_trace_output():
    leaked_secret = "policy-token-abcdef123456"
    client = FakeChatClient(
        [
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
                        "answer": f"Use api_key={leaked_secret} for the vendor portal.",
                        "policy_id": "POL-1",
                        "citations": ["POL-1"],
                        "action": "answer_policy_question",
                    }
                ),
                tool_calls=[],
                prompt_tokens=100,
                completion_tokens=30,
                estimated_cost_usd=0.00002,
            ),
        ]
    )

    result = await AgentRunner(client=client).execute(
        make_policy_scenario("How do I access the vendor portal?"), "run-policy-redact"
    )

    finalize_event = next(event for event in result.trace_events if event.details["node"] == "finalize")
    assert leaked_secret in result.output["answer"]
    assert leaked_secret not in json.dumps(finalize_event.details)
    assert "[redacted]" in json.dumps(finalize_event.details)


async def test_agent_runner_without_api_key_raises_not_configured():
    from app.core.config import Settings
    from app.services.llm_client import LLMClient, LLMNotConfiguredError

    client = LLMClient(settings=Settings(openrouter_api_key=None))
    runner = AgentRunner(client=client)

    with pytest.raises(LLMNotConfiguredError):
        await runner.execute(make_scenario("Hello"), "run-4")
