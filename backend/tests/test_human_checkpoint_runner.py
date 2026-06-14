"""Unit tests for HumanCheckpointRunner's pause/resume flow against a fake
chat client — no network calls."""

import json

import pytest

from app.runners.human_checkpoint_runner import HumanCheckpointRunner
from app.schemas.scenario import Scenario
from app.services.llm_client import ChatResponse, ToolCall
from tests.fakes import FakeChatClient

pytestmark = pytest.mark.anyio


def make_scenario(input_text: str, **kwargs) -> Scenario:
    return Scenario(id="test-scenario", name="Test scenario", input=input_text, **kwargs)


SECRET_DIFF = """\
diff --git a/app/config.py b/app/config.py
index 4a3f2c1..8b9d3e2 100644
--- a/app/config.py
+++ b/app/config.py
@@ -1,2 +1,3 @@
 DEBUG = False
 DATABASE_URL = "sqlite:///app.db"
+OPENAI_API_KEY = "sk-live-abcdef1234567890"
"""

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


def make_secret_diff_scenario() -> Scenario:
    return Scenario(
        id="diff-hardcoded-secret",
        name="Git Diff Review - Hardcoded Secret",
        family="git_diff_review",
        input=SECRET_DIFF,
    )


def make_missing_test_diff_scenario() -> Scenario:
    return Scenario(
        id="diff-missing-test-coverage",
        name="Git Diff Review - Missing Test Coverage",
        family="git_diff_review",
        input=MISSING_TEST_DIFF,
    )


def billing_responses() -> list[ChatResponse]:
    return [
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


async def test_human_checkpoint_pauses_for_high_impact_action():
    client = FakeChatClient(billing_responses())
    runner = HumanCheckpointRunner(client=client)

    result = await runner.execute(
        make_scenario("I was charged twice for order #1234. jane.doe@example.com"), "run-1"
    )

    assert result.actions == []
    assert result.pending_approval is not None
    assert result.pending_approval.action == "escalate_billing_review"
    assert result.output["intent"] == "billing_issue"
    assert client.calls == 3
    assert result.pending_approval.details["triggers"][0]["kind"] == "risky_action"


async def test_human_checkpoint_resume_approve():
    client = FakeChatClient(billing_responses())
    runner = HumanCheckpointRunner(client=client)

    await runner.execute(
        make_scenario("I was charged twice for order #1234. jane.doe@example.com"), "run-2"
    )
    result = await runner.resume("run-2", "approve")

    assert result.pending_approval is None
    assert result.actions == ["escalate_billing_review"]
    assert result.output["approval_decision"] == "approve"
    # token totals are cumulative across the whole run, including the
    # decide step that ran before the pause.
    assert result.prompt_tokens == 370
    assert result.completion_tokens == 70


async def test_human_checkpoint_resume_reject_falls_back():
    client = FakeChatClient(billing_responses())
    runner = HumanCheckpointRunner(client=client)

    await runner.execute(
        make_scenario("I was charged twice for order #1234. jane.doe@example.com"), "run-3"
    )
    result = await runner.resume("run-3", "reject")

    assert result.actions == ["escalate_general_review"]
    assert result.output["approval_decision"] == "reject"
    assert result.output["proposed_action"] == "escalate_billing_review"


async def test_human_checkpoint_no_approval_needed_for_low_impact_action():
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
    runner = HumanCheckpointRunner(client=client)

    result = await runner.execute(make_scenario("Where is my package?"), "run-4")

    assert result.pending_approval is None
    assert result.actions == ["request_order_id"]


async def test_human_checkpoint_pauses_for_missing_required_field():
    client = FakeChatClient(
        [
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=80, completion_tokens=10,
                estimated_cost_usd=0.00005,
            ),
            ChatResponse(
                content=json.dumps(
                    {"intent": "shipping_issue", "action": "request_order_id", "confidence": 0.9}
                ),
                tool_calls=[],
                prompt_tokens=90,
                completion_tokens=15,
                estimated_cost_usd=0.00006,
            ),
        ]
    )
    runner = HumanCheckpointRunner(client=client)

    result = await runner.execute(
        make_scenario("Where is my package?", required_fields=["order_id"]),
        "run-missing-fields",
    )

    assert result.pending_approval is not None
    assert result.pending_approval.action == "request_order_id"
    triggers = result.pending_approval.details["triggers"]
    assert triggers[0]["kind"] == "missing_fields"
    assert triggers[0]["missing_fields"] == ["order_id"]


async def test_human_checkpoint_pauses_for_low_confidence():
    client = FakeChatClient(
        [
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=80, completion_tokens=10,
                estimated_cost_usd=0.00005,
            ),
            ChatResponse(
                content=json.dumps(
                    {"intent": "shipping_issue", "action": "request_order_id", "confidence": 0.3}
                ),
                tool_calls=[],
                prompt_tokens=90,
                completion_tokens=15,
                estimated_cost_usd=0.00006,
            ),
        ]
    )
    runner = HumanCheckpointRunner(client=client)

    result = await runner.execute(make_scenario("Where is my package?"), "run-low-confidence")

    assert result.pending_approval is not None
    assert result.pending_approval.action == "request_order_id"
    assert result.confidence == 0.3
    triggers = result.pending_approval.details["triggers"]
    assert triggers[0]["kind"] == "low_confidence"
    assert triggers[0]["confidence"] == 0.3


async def test_human_checkpoint_pauses_for_conflicting_signals():
    client = FakeChatClient(
        [
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=80, completion_tokens=10,
                estimated_cost_usd=0.00005,
            ),
            ChatResponse(
                content="not valid json",
                tool_calls=[],
                prompt_tokens=50,
                completion_tokens=5,
                estimated_cost_usd=0.00001,
            ),
            ChatResponse(
                content=json.dumps(
                    {"intent": "shipping_issue", "action": "request_order_id", "confidence": 0.9}
                ),
                tool_calls=[],
                prompt_tokens=90,
                completion_tokens=15,
                estimated_cost_usd=0.00006,
            ),
        ]
    )
    runner = HumanCheckpointRunner(client=client)

    result = await runner.execute(
        make_scenario("Where is my package?"), "run-conflicting-signals"
    )

    assert result.pending_approval is not None
    assert result.retries == 1
    triggers = result.pending_approval.details["triggers"]
    assert triggers[0]["kind"] == "conflicting_signals"
    assert triggers[0]["retries"] == 1


async def test_human_checkpoint_diff_review_pauses_for_request_changes():
    client = FakeChatClient(
        [
            ChatResponse(
                content="", tool_calls=[], prompt_tokens=70, completion_tokens=10,
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
                                "message": "Hardcoded credential found",
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
    runner = HumanCheckpointRunner(client=client)

    pending = await runner.execute(make_secret_diff_scenario(), "run-diff-human-secret")

    assert pending.actions == []
    assert pending.pending_approval is not None
    assert pending.pending_approval.action == "request_changes"

    result = await runner.resume("run-diff-human-secret", "approve")

    assert result.pending_approval is None
    assert result.actions == ["request_changes"]
    assert result.output["approval_decision"] == "approve"


async def test_human_checkpoint_diff_review_no_pause_for_comment():
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
    runner = HumanCheckpointRunner(client=client)

    result = await runner.execute(make_missing_test_diff_scenario(), "run-diff-human-tests")

    assert result.pending_approval is None
    assert result.output["verdict"] == "comment"
    assert result.actions == ["comment_on_pr"]


async def test_human_checkpoint_without_api_key_raises_not_configured():
    from app.core.config import Settings
    from app.services.llm_client import LLMClient, LLMNotConfiguredError

    client = LLMClient(settings=Settings(openrouter_api_key=None))
    runner = HumanCheckpointRunner(client=client)

    with pytest.raises(LLMNotConfiguredError):
        await runner.execute(make_scenario("Hello"), "run-5")
