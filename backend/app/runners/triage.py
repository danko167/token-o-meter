"""Shared vocabulary for the customer-email-triage scenario family.

Every runner (rules, workflow, llm, ...) classifies into the same intent
labels and chooses from the same action vocabulary, and extracts entities
the same way. That's what makes their outputs directly comparable."""

import re

ORDER_ID_RE = re.compile(r"(?:order\s*)?#(\d+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

INTENT_LABELS: list[str] = [
    "billing_issue",
    "shipping_issue",
    "account_issue",
    "cancellation",
    "product_question",
    "unknown",
]

# keyword -> intent decision table; first match wins, ordered by specificity.
INTENT_RULES: list[tuple[str, list[str]]] = [
    (
        "billing_issue",
        ["charged twice", "double charge", "refund", "charged", "invoice", "billing", "payment"],
    ),
    ("shipping_issue", ["tracking", "shipped", "delivery", "delayed", "package", "arrive"]),
    ("account_issue", ["password", "login", "log in", "account locked", "reset"]),
    ("cancellation", ["cancel", "unsubscribe", "stop my"]),
    ("product_question", ["how do i", "does it", "compatible", "feature"]),
]

# action -> human-readable description. Shared by WorkflowRunner's business
# rules and the LLMRunner's prompt/validation so both choose from the same
# set of next steps.
ALLOWED_ACTIONS: dict[str, str] = {
    "request_order_id": "Ask the customer for their order ID before proceeding.",
    "escalate_billing_review": "Flag a billing discrepancy for manual review by finance.",
    "provide_tracking_update": "Share the current shipping/tracking status with the customer.",
    "escalate_shipping_review": "Flag a shipping issue for manual review by logistics.",
    "send_password_reset": "Send the customer a password reset link.",
    "process_cancellation": "Process the customer's cancellation request per policy.",
    "answer_product_question": "Answer the customer's product question directly.",
    "escalate_general_review": "Flag the email for manual review — intent unclear.",
}


def extract_entities(text: str) -> dict[str, str]:
    """Pull an order id and/or email address out of free text, if present."""
    entities: dict[str, str] = {}
    if match := ORDER_ID_RE.search(text):
        entities["order_id"] = match.group(1)
    if match := EMAIL_RE.search(text):
        entities["customer_email"] = match.group(0)
    return entities
