"""Small mock policy corpus and retrieval helper for Policy QA scenarios."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDoc:
    id: str
    title: str
    category: str
    text: str


POLICIES: dict[str, PolicyDoc] = {
    "refund-policy": PolicyDoc(
        id="refund-policy",
        title="Refund Policy",
        category="refunds",
        text=(
            "Customers may request a refund within 30 days of delivery when an item is "
            "unused or defective. Refunds after 30 days require supervisor review. "
            "Shipping fees are not refunded unless the shipment was lost or the wrong "
            "item was sent."
        ),
    ),
    "shipping-policy": PolicyDoc(
        id="shipping-policy",
        title="Shipping Policy",
        category="shipping",
        text=(
            "Orders normally ship within two business days. Once an order has shipped, "
            "customers should use the tracking link for delivery updates. Lost shipments "
            "may be replaced or refunded after carrier investigation."
        ),
    ),
    "cancellation-policy": PolicyDoc(
        id="cancellation-policy",
        title="Cancellation Policy",
        category="cancellations",
        text=(
            "Customers may cancel an order until it enters packing. Orders that have "
            "already shipped cannot be cancelled; the customer may refuse delivery or "
            "start a return after delivery."
        ),
    ),
    "warranty-policy": PolicyDoc(
        id="warranty-policy",
        title="Warranty Policy",
        category="warranty",
        text=(
            "Most products include a one-year limited warranty covering manufacturing "
            "defects. Accidental damage, normal wear, and unauthorized repairs are not "
            "covered by warranty."
        ),
    ),
    "account-security-policy": PolicyDoc(
        id="account-security-policy",
        title="Account Security Policy",
        category="account_security",
        text=(
            "Account changes require identity verification. Support may send a password "
            "reset link, but agents must not reveal private account details before "
            "verification is complete."
        ),
    ),
}


SEARCH_POLICY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_policy",
        "description": "Search the internal policy corpus for passages relevant to a question.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The user's policy question."},
                "top_k": {"type": "integer", "description": "Maximum passages to return."},
            },
            "required": ["query"],
        },
    },
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in {"the", "and", "for", "that", "with"}
    }


def search_policy(query: str, top_k: int = 2) -> list[dict[str, str]]:
    """Return the highest-scoring policy docs for a lightweight keyword search."""
    query_tokens = _tokens(query)
    scored: list[tuple[int, PolicyDoc]] = []

    for policy in POLICIES.values():
        haystack = _tokens(f"{policy.title} {policy.category} {policy.text}")
        score = len(query_tokens & haystack)
        if score:
            scored.append((score, policy))

    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [
        {
            "policy_id": policy.id,
            "title": policy.title,
            "category": policy.category,
            "text": policy.text,
        }
        for _, policy in scored[: max(1, top_k)]
    ]
