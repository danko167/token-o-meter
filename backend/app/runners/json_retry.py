"""Shared retry loop for LLM JSON responses."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from app.services.llm_client import LLMClient

MAX_ATTEMPTS = 2

T = TypeVar("T")


@dataclass(frozen=True)
class JsonAttempt:
    data: dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    error: Exception | None = None


@dataclass(frozen=True)
class JsonRetryResult(Generic[T]):
    value: T
    attempt: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    retries: int


async def retry_valid_json(
    fetch: Callable[[], Awaitable[JsonAttempt]],
    parse: Callable[[dict[str, Any]], T],
    *,
    attempts: int = MAX_ATTEMPTS,
) -> JsonRetryResult[T]:
    prompt_tokens = 0
    completion_tokens = 0
    estimated_cost_usd = 0.0
    retries = 0
    last_error: Exception | None = None

    for attempt in range(attempts):
        response = await fetch()
        prompt_tokens += response.prompt_tokens
        completion_tokens += response.completion_tokens
        estimated_cost_usd += response.estimated_cost_usd

        if response.error is not None:
            last_error = response.error
            retries += 1
            continue

        try:
            value = parse(response.data)
        except (KeyError, TypeError) as exc:
            last_error = exc
            retries += 1
            continue

        return JsonRetryResult(
            value=value,
            attempt=attempt + 1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost_usd,
            retries=retries,
        )

    raise RuntimeError(
        f"LLM did not return a usable JSON object after {attempts} attempts: {last_error}"
    )


async def chat_json_fetch(client: LLMClient, messages: list[dict[str, Any]]) -> JsonAttempt:
    """`fetch` for `retry_valid_json`: a JSON-mode chat completion over `messages`."""
    final = await client.chat(messages, json_mode=True)
    try:
        data = json.loads(final.content or "{}")
    except json.JSONDecodeError as exc:
        return JsonAttempt(
            data={},
            prompt_tokens=final.prompt_tokens,
            completion_tokens=final.completion_tokens,
            estimated_cost_usd=final.estimated_cost_usd,
            error=exc,
        )
    return JsonAttempt(
        data=data,
        prompt_tokens=final.prompt_tokens,
        completion_tokens=final.completion_tokens,
        estimated_cost_usd=final.estimated_cost_usd,
    )
