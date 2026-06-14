"""Shared Policy QA vocabulary and parsing helpers."""

from __future__ import annotations

from typing import Any

from app.services.checkpoint_policy import parse_confidence
from app.services.policy_docs import POLICIES

ACTION_NAME = "provide_policy_answer"
REJECT_ACTION = "escalate_policy_review"

CATEGORIES: dict[str, list[str]] = {
    "refunds": ["refund", "money back", "return", "defective", "wrong item"],
    "shipping": ["ship", "shipping", "tracking", "delivery", "lost", "carrier"],
    "cancellations": ["cancel", "cancellation", "shipped", "packing"],
    "warranty": ["warranty", "defect", "repair", "damage", "covered"],
    "account_security": ["password", "account", "verification", "security", "private"],
}

POLICY_ID_BY_CATEGORY = {policy.category: policy.id for policy in POLICIES.values()}

CATEGORY_ALIASES = {
    "refund": "refunds",
    "refund_policy": "refunds",
    "return": "refunds",
    "returns": "refunds",
    "return_policy": "refunds",
    "cancellation": "cancellations",
    "cancel": "cancellations",
    "shipping_policy": "shipping",
    "warranty_policy": "warranty",
    "account": "account_security",
    "security": "account_security",
}

SYSTEM_PROMPT = """You are a policy question answering assistant. Use the search_policy tool
to retrieve relevant internal policy passages before answering. Reply with a JSON object with:
- "category": the policy category
- "policy_id": the cited policy id
- "answer": a concise answer grounded in the policy text
- "citations": a list of cited policy ids
- "action": "provide_policy_answer" or "escalate_policy_review"
- "confidence": a number from 0.0 to 1.0 indicating how confident you are that "answer" is
correct and fully grounded in the retrieved policy

Do not invent policy. If the retrieved policy does not answer the question, escalate."""

NO_RETRIEVAL_SYSTEM_PROMPT = """You are a policy question answering assistant without tool access.
Answer from the question alone as JSON with fields category, policy_id, answer, citations, action.
Use action "provide_policy_answer" only when you are confident; otherwise use
"escalate_policy_review"."""

FINAL_ANSWER_PROMPT = "Now reply with ONLY the JSON object as specified."

FALLBACK_PROPOSAL = {
    "output": {
        "category": "unknown",
        "policy_id": None,
        "answer": "I could not confidently answer from the available policy information.",
    },
    "actions": [REJECT_ACTION],
    "action": REJECT_ACTION,
    "confidence": 0.0,
}


def classify_category(question: str) -> str:
    text = question.lower()
    best_category = "unknown"
    best_score = 0
    for category, keywords in CATEGORIES.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_category = category
            best_score = score
    return best_category


def normalize_category(category: str) -> str:
    normalized = category.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in CATEGORIES:
        return normalized
    return CATEGORY_ALIASES.get(normalized, category)


def extract_best_sentence(question: str, policy_id: str | None) -> str:
    if not policy_id or policy_id not in POLICIES:
        return "No matching policy was found."

    question_terms = set(question.lower().replace("?", "").split())
    sentences = [sentence.strip() for sentence in POLICIES[policy_id].text.split(".") if sentence]
    best = max(
        sentences,
        key=lambda sentence: len(question_terms & set(sentence.lower().split())),
        default=POLICIES[policy_id].text,
    )
    return best.rstrip(".") + "."


def parse_policy_proposal(data: dict[str, Any], retrieved: list[dict[str, Any]]) -> dict[str, Any]:
    action = str(data.get("action") or ACTION_NAME)
    if action not in {ACTION_NAME, REJECT_ACTION}:
        action = REJECT_ACTION

    policy_id = data.get("policy_id")
    if not policy_id and retrieved:
        policy_id = retrieved[0]["policy_id"]

    category = normalize_category(str(data.get("category") or "unknown"))
    if not policy_id and category in POLICY_ID_BY_CATEGORY:
        policy_id = POLICY_ID_BY_CATEGORY[category]
    if category == "unknown" and policy_id in POLICIES:
        category = POLICIES[str(policy_id)].category

    answer = str(data.get("answer") or "").strip()
    if not answer and policy_id:
        answer = extract_best_sentence("", str(policy_id))

    citations = data.get("citations")
    if not isinstance(citations, list):
        citations = [policy_id] if policy_id else []

    output = {
        "category": category,
        "policy_id": str(policy_id) if policy_id else None,
        "answer": answer,
        "citations": [str(citation) for citation in citations if citation],
    }
    if retrieved:
        output["retrieved_policy_ids"] = [str(item["policy_id"]) for item in retrieved]

    confidence = parse_confidence(data.get("confidence"))
    return {"output": output, "actions": [action], "action": action, "confidence": confidence}
