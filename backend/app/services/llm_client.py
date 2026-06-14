"""Provider-aware wrapper around OpenAI-compatible chat completions APIs.

OpenRouter remains the default provider. Direct OpenAI models are selected by
passing an `llm_model` value namespaced as `openai:<model>`, for example
`openai:gpt-4.1-mini`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.core.config import Settings, get_settings
from app.services.llm_models import (
    OPENAI_PROVIDER,
    OPENROUTER_PROVIDER,
    find_direct_openai_model,
    model_costs,
)

logger = logging.getLogger(__name__)

_model_override: ContextVar[str | None] = ContextVar("llm_model_override", default=None)


class LLMNotConfiguredError(RuntimeError):
    """Raised when the selected LLM provider is missing an API key."""


@dataclass(frozen=True)
class ModelSelection:
    provider: str
    api_model: str
    pricing_model: str


class LLMResponse:
    def __init__(
        self,
        data: dict,
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float,
    ) -> None:
        self.data = data
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.estimated_cost_usd = estimated_cost_usd


class ToolCall:
    """A single function call requested by the model."""

    def __init__(self, id: str, name: str, arguments: str) -> None:
        self.id = id
        self.name = name
        self.arguments = arguments


class ChatResponse:
    """Result of a general chat completion, optionally with tool calls."""

    def __init__(
        self,
        content: str,
        tool_calls: list[ToolCall],
        prompt_tokens: int,
        completion_tokens: int,
        estimated_cost_usd: float,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.estimated_cost_usd = estimated_cost_usd


class LLMClient:
    """Chat completions against the selected OpenAI-compatible provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._clients: dict[str, AsyncOpenAI] = {}

    def _get_client(self, provider: str | None = None) -> AsyncOpenAI:
        provider = provider or self.selection.provider
        if provider == OPENAI_PROVIDER:
            if not self._settings.openai_api_key:
                raise LLMNotConfiguredError(
                    "JEAI_OPENAI_API_KEY is not set - add it to your .env file "
                    "to enable direct OpenAI models."
                )
            if provider not in self._clients:
                self._clients[provider] = AsyncOpenAI(
                    api_key=self._settings.openai_api_key,
                    base_url=self._settings.openai_base_url,
                    max_retries=0,
                )
            return self._clients[provider]

        if not self._settings.llm_api_key:
            raise LLMNotConfiguredError(
                "JEAI_OPENROUTER_API_KEY is not set - add it to your .env file "
                "to enable LLM-based runners."
            )
        if provider not in self._clients:
            self._clients[provider] = AsyncOpenAI(
                api_key=self._settings.llm_api_key,
                base_url=self._settings.llm_base_url,
                max_retries=0,
            )
        return self._clients[provider]

    @property
    def selection(self) -> ModelSelection:
        requested = _model_override.get()
        if requested is None:
            return ModelSelection(
                provider=OPENROUTER_PROVIDER,
                api_model=self._settings.llm_model,
                pricing_model=self._settings.llm_model,
            )

        if requested.startswith("openai:"):
            configured = find_direct_openai_model(requested)
            return ModelSelection(
                provider=OPENAI_PROVIDER,
                api_model=configured.api_model if configured else requested.removeprefix("openai:"),
                pricing_model=requested,
            )

        return ModelSelection(
            provider=OPENROUTER_PROVIDER,
            api_model=requested,
            pricing_model=requested,
        )

    @property
    def model(self) -> str:
        return self.selection.api_model

    def _cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        input_cost, output_cost = model_costs(
            self.selection.pricing_model,
            self._settings.llm_input_cost_per_million,
            self._settings.llm_output_cost_per_million,
        )
        return (
            prompt_tokens / 1_000_000 * input_cost
            + completion_tokens / 1_000_000 * output_cost
        )

    async def complete_json(self, system: str, user: str) -> LLMResponse:
        """Run a single chat completion and parse the reply as JSON."""
        selection = self.selection
        client = self._get_client(selection.provider)
        response = await client.chat.completions.create(
            model=selection.api_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM response was not valid JSON: %r", content[:200])
            data = {}

        return LLMResponse(
            data=data,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=self._cost(prompt_tokens, completion_tokens),
        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        json_mode: bool = False,
    ) -> ChatResponse:
        """General chat completion with optional tool/function-calling."""
        selection = self.selection
        client = self._get_client(selection.provider)
        kwargs: dict = {}
        if tools:
            kwargs["tools"] = tools
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(
            model=selection.api_model,
            messages=messages,
            temperature=0,
            **kwargs,
        )

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        message = response.choices[0].message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
            for tc in (message.tool_calls or [])
        ]

        return ChatResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=self._cost(prompt_tokens, completion_tokens),
        )


@contextmanager
def use_llm_model(model: str | None) -> Iterator[None]:
    token = _model_override.set(model)
    try:
        yield
    finally:
        _model_override.reset(token)
