"""Unit tests for LLMRunner against a fake LLM client — no network calls."""

import pytest

from app.runners.llm_runner import LLMRunner
from app.schemas.scenario import Scenario
from app.services.llm_client import LLMResponse

pytestmark = pytest.mark.anyio


class FakeLLMClient:
    """Returns a queued sequence of responses, one per call."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete_json(self, system: str, user: str) -> LLMResponse:
        self.calls += 1
        return self._responses[self.calls - 1]


def make_scenario() -> Scenario:
    return Scenario(
        id="test-scenario",
        name="Test scenario",
        input="I was charged twice for order #1234. Please help, jane.doe@example.com",
    )


async def test_llm_runner_returns_structured_output():
    client = FakeLLMClient(
        [
            LLMResponse(
                data={
                    "intent": "billing_issue",
                    "order_id": "1234",
                    "customer_email": "jane.doe@example.com",
                    "action": "escalate_billing_review",
                },
                prompt_tokens=120,
                completion_tokens=30,
                estimated_cost_usd=0.0001,
            )
        ]
    )
    runner = LLMRunner(client=client)

    result = await runner.execute(make_scenario(), "test-run")

    assert result.output == {
        "intent": "billing_issue",
        "order_id": "1234",
        "customer_email": "jane.doe@example.com",
    }
    assert result.actions == ["escalate_billing_review"]
    assert result.confidence == 1.0
    assert result.prompt_tokens == 120
    assert result.completion_tokens == 30
    assert result.estimated_cost_usd == pytest.approx(0.0001)
    assert result.retries == 0
    assert client.calls == 1


async def test_llm_runner_retries_once_on_malformed_response():
    client = FakeLLMClient(
        [
            LLMResponse(
                data={}, prompt_tokens=100, completion_tokens=5, estimated_cost_usd=0.00005
            ),
            LLMResponse(
                data={"intent": "shipping_issue", "action": "request_order_id"},
                prompt_tokens=100,
                completion_tokens=10,
                estimated_cost_usd=0.0001,
            ),
        ]
    )
    runner = LLMRunner(client=client)

    result = await runner.execute(make_scenario(), "test-run")

    assert result.output == {"intent": "shipping_issue"}
    assert result.actions == ["request_order_id"]
    assert result.retries == 1
    # token/cost totals accumulate across both attempts
    assert result.prompt_tokens == 200
    assert result.completion_tokens == 15
    assert client.calls == 2


async def test_llm_runner_raises_after_exhausting_retries():
    client = FakeLLMClient(
        [
            LLMResponse(data={}, prompt_tokens=10, completion_tokens=1, estimated_cost_usd=0.0),
            LLMResponse(data={}, prompt_tokens=10, completion_tokens=1, estimated_cost_usd=0.0),
        ]
    )
    runner = LLMRunner(client=client)

    with pytest.raises(RuntimeError, match="did not return a usable JSON object"):
        await runner.execute(make_scenario(), "test-run")

    assert client.calls == 2


async def test_llm_runner_without_api_key_raises_not_configured():
    from app.core.config import Settings
    from app.services.llm_client import LLMClient, LLMNotConfiguredError

    client = LLMClient(settings=Settings(openrouter_api_key=None))
    runner = LLMRunner(client=client)

    with pytest.raises(LLMNotConfiguredError):
        await runner.execute(make_scenario(), "test-run")


def test_llm_client_disables_sdk_retries():
    from app.core.config import Settings
    from app.services.llm_client import LLMClient

    client = LLMClient(settings=Settings(openrouter_api_key="test-key"))._get_client()

    assert client.max_retries == 0


def test_llm_client_selects_direct_openai_model():
    from app.core.config import Settings
    from app.services.llm_client import LLMClient, use_llm_model

    llm = LLMClient(
        settings=Settings(openrouter_api_key=None, openai_api_key="test-openai-key")
    )

    with use_llm_model("openai:gpt-4.1-mini"):
        assert llm.selection.provider == "openai"
        assert llm.selection.api_model == "gpt-4.1-mini"
        assert llm.selection.pricing_model == "openai:gpt-4.1-mini"
        assert llm._get_client().max_retries == 0


def test_llm_client_direct_openai_requires_openai_key():
    from app.core.config import Settings
    from app.services.llm_client import LLMClient, LLMNotConfiguredError, use_llm_model

    llm = LLMClient(
        settings=Settings(openrouter_api_key="test-openrouter-key", openai_api_key="")
    )

    with use_llm_model("openai:gpt-4.1-mini"):
        with pytest.raises(LLMNotConfiguredError, match="JEAI_OPENAI_API_KEY"):
            llm._get_client()
