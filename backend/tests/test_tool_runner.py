"""Unit tests for ToolRunner against a fake chat client — no network calls."""

import json

import pytest

from app.runners.tool_runner import ToolRunner
from app.schemas.scenario import Scenario
from app.services.llm_client import ChatResponse, ToolCall
from tests.fakes import FakeChatClient

pytestmark = pytest.mark.anyio


def make_scenario() -> Scenario:
    return Scenario(
        id="test-scenario",
        name="Test scenario",
        input="I was charged twice for order #1234. Please help, jane.doe@example.com",
    )


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


async def test_tool_runner_calls_lookup_order_then_answers():
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
    runner = ToolRunner(client=client)

    result = await runner.execute(make_scenario(), "run-1")

    assert result.output["intent"] == "billing_issue"
    assert result.output["order_id"] == "1234"
    assert result.output["order_status"] == "delivered, charged twice"
    assert result.output["tool_calls"][0]["name"] == "lookup_order"
    assert result.output["tool_calls"][0]["order_id"] == "1234"
    assert result.output["tool_calls"][0]["found"] is True
    assert result.output["tool_calls"][0]["duration_ms"] >= 0
    assert result.actions == ["escalate_billing_review"]
    assert result.prompt_tokens == 250
    assert result.completion_tokens == 60
    assert result.retries == 0
    assert client.calls == 2


async def test_tool_runner_skips_tool_when_not_needed():
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
    runner = ToolRunner(client=client)

    result = await runner.execute(make_scenario(), "run-2")

    assert result.output == {"intent": "shipping_issue"}
    assert result.actions == ["request_order_id"]
    assert "tool_calls" not in result.output
    assert client.calls == 2


async def test_tool_runner_retries_on_malformed_final_json():
    client = FakeChatClient(
        [
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=10, completion_tokens=1,
                estimated_cost_usd=0.0,
            ),
            ChatResponse(
                content="not json", tool_calls=[], prompt_tokens=10, completion_tokens=1,
                estimated_cost_usd=0.0,
            ),
            ChatResponse(
                content=json.dumps({"intent": "unknown", "action": "escalate_general_review"}),
                tool_calls=[],
                prompt_tokens=10,
                completion_tokens=1,
                estimated_cost_usd=0.0,
            ),
        ]
    )
    runner = ToolRunner(client=client)

    result = await runner.execute(make_scenario(), "run-3")

    assert result.output == {"intent": "unknown"}
    assert result.retries == 1
    assert client.calls == 3


async def test_tool_runner_diff_review_reads_file_then_answers():
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

    result = await ToolRunner(client=client).execute(
        make_missing_test_diff_scenario(), "run-diff-tool"
    )

    assert result.output["verdict"] == "comment"
    assert result.output["files_read"] == ["tests/test_payments.py"]
    assert result.actions == ["comment_on_pr"]
    assert client.calls == 2


async def test_tool_runner_without_api_key_raises_not_configured():
    from app.core.config import Settings
    from app.services.llm_client import LLMClient, LLMNotConfiguredError

    client = LLMClient(settings=Settings(openrouter_api_key=None))
    runner = ToolRunner(client=client)

    with pytest.raises(LLMNotConfiguredError):
        await runner.execute(make_scenario(), "run-4")
