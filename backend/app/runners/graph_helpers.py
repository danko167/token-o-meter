"""Shared helpers for LangGraph agent nodes.

Used by `agent_graph.py`, `diff_agent_graph.py`, and `policy_agent_graph.py` to
build `TraceEvent`s and redacted/truncated previews of conversation messages
and node output for the run trace.
"""

import re
import time
from datetime import UTC, datetime
from typing import Any

from app.schemas.run import TraceEvent

#: How many of the most recent messages to include in a node's trace preview.
MAX_TRACE_MESSAGES = 5
#: Max characters before a previewed string is truncated.
MAX_TRACE_TEXT_CHARS = 700


def node_event(
    name: str,
    start: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    details: dict[str, Any] | None = None,
) -> TraceEvent:
    return TraceEvent(
        name=f"Graph node: {name}",
        kind="runner",
        timestamp=datetime.now(UTC),
        duration_ms=round((time.perf_counter() - start) * 1000, 1),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated_cost_usd,
        details={"node": name, **(details or {})},
    )


def message_previews(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [message_preview(message) for message in messages[-MAX_TRACE_MESSAGES:]]


def message_preview(message: dict[str, Any]) -> dict[str, Any]:
    preview: dict[str, Any] = {"role": message.get("role", "unknown")}
    if "content" in message:
        preview["content"] = truncate_text(str(message.get("content") or ""))
    if "tool_call_id" in message:
        preview["tool_call_id"] = truncate_text(str(message["tool_call_id"]), 120)
    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        preview["tool_calls"] = [
            {
                "name": call.get("function", {}).get("name"),
                "arguments": truncate_text(str(call.get("function", {}).get("arguments") or "")),
            }
            for call in tool_calls
            if isinstance(call, dict)
        ]
    return preview


def truncate_value(value: Any) -> Any:
    if isinstance(value, str):
        return truncate_text(value)
    if isinstance(value, dict):
        return {str(key): truncate_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [truncate_value(item) for item in value[:20]]
    return value


def truncate_text(text: str, limit: int = MAX_TRACE_TEXT_CHARS) -> str:
    redacted = redact(text)
    if len(redacted) <= limit:
        return redacted
    return f"{redacted[:limit]}... [truncated {len(redacted) - limit} chars]"


def redact(text: str) -> str:
    redacted = re.sub(
        r"(?i)(api[_-]?key|token|secret|password)(\s*[:=]\s*)['\"]?[^'\"\s,}]+",
        r"\1\2[redacted]",
        text,
    )
    redacted = re.sub(
        r"(?i)(authorization\s*:\s*bearer\s+)[^\s,}]+",
        r"\1[redacted]",
        redacted,
    )
    return redacted
