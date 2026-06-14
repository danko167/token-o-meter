"""Shared test doubles for LLM-backed runners — no network calls."""

from app.services.llm_client import ChatResponse


class FakeChatClient:
    """Returns a queued sequence of ChatResponses, one per `chat()` call."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat(
        self, messages: list[dict], tools: list[dict] | None = None, json_mode: bool = False
    ) -> ChatResponse:
        self.calls += 1
        return self._responses[self.calls - 1]
