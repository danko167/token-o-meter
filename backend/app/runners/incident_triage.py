"""Shared Incident Triage vocabulary and parsing helpers."""

from __future__ import annotations

import re
from typing import Any

from app.services.checkpoint_policy import parse_confidence

SEVERITY_LABELS = ["low", "medium", "high", "critical"]

CATEGORY_LABELS = [
    "deployment_regression",
    "resource_exhaustion",
    "transient",
    "dependency_outage",
    "unknown",
]

ALLOWED_ACTIONS: dict[str, str] = {
    "acknowledge": "Acknowledge the alert; no remediation is needed.",
    "restart_service": "Restart the affected service.",
    "rollback_deploy": "Roll back the deploy correlated with this regression.",
    "page_oncall": "Page the on-call engineer.",
    "escalate_incident": "Escalate to the incident commander for manual triage.",
}

#: Default next action for each category, used by the workflow runner and as a
#: fallback when a model-proposed action isn't in ALLOWED_ACTIONS.
CATEGORY_TO_ACTION: dict[str, str] = {
    "deployment_regression": "rollback_deploy",
    "resource_exhaustion": "restart_service",
    "transient": "acknowledge",
    "dependency_outage": "page_oncall",
    "unknown": "escalate_incident",
}

CATEGORY_TO_SEVERITY: dict[str, str] = {
    "deployment_regression": "high",
    "resource_exhaustion": "medium",
    "transient": "low",
    "dependency_outage": "critical",
    "unknown": "medium",
}

SUMMARY_TEMPLATES: dict[str, str] = {
    "deployment_regression": (
        "A recent deploy appears to have caused a regression; recommend rolling back."
    ),
    "resource_exhaustion": (
        "Resource usage is climbing toward exhaustion; recommend restarting the affected service."
    ),
    "transient": (
        "The alert appears to be a transient spike that has already recovered; "
        "no remediation needed."
    ),
    "dependency_outage": (
        "An upstream or downstream dependency appears to be degraded; recommend paging on-call."
    ),
    "unknown": "Unable to confidently classify this alert; escalating for manual triage.",
}

#: Action a HumanCheckpointRunner falls back to if a risky proposal is
#: rejected by a human reviewer.
REJECT_ACTION = "escalate_incident"

_RECOVERED_RE = re.compile(r"recovered|resolved|back to normal")
_MINUTES_AGO_RE = re.compile(r"\d+\s*minutes?\s*ago")
_RESOURCE_RE = re.compile(r"(memory|cpu).{0,60}(climb|increasing|grow|leak)")
_DEPENDENCY_RE = re.compile(r"dependency|downstream|third-party|upstream")


def classify_incident(alert_text: str) -> dict[str, Any]:
    """Deterministically classify an alert from its text alone."""
    text = alert_text.lower()

    if _RECOVERED_RE.search(text):
        category = "transient"
    elif "deploy" in text and _MINUTES_AGO_RE.search(text):
        category = "deployment_regression"
    elif _RESOURCE_RE.search(text):
        category = "resource_exhaustion"
    elif _DEPENDENCY_RE.search(text):
        category = "dependency_outage"
    else:
        category = "unknown"

    return {
        "severity": CATEGORY_TO_SEVERITY[category],
        "category": category,
        "summary": SUMMARY_TEMPLATES[category],
    }


# --- prompts ----------------------------------------------------------------

ACTION_LINES = "\n".join(f"- {name}: {desc}" for name, desc in ALLOWED_ACTIONS.items())

SYSTEM_PROMPT = f"""You are an on-call incident triage assistant with access to a \
`check_service_status` tool that returns a service's current error rate, latency, \
resource usage, and recent deploy/incident history.

If the alert names a specific service, call check_service_status to check its current \
state before deciding. Then reply with ONLY a JSON object with these fields:
- "severity": one of {SEVERITY_LABELS}
- "category": one of {CATEGORY_LABELS}
- "service": the name of the affected service, or null if none is named
- "summary": a one-sentence summary of the incident
- "action": the single most appropriate next step, one of:
{ACTION_LINES}
- "confidence": a number from 0.0 to 1.0 indicating how confident you are in this decision

Reply with ONLY the JSON object — no markdown, no commentary."""

NO_CONTEXT_SYSTEM_PROMPT = f"""You are an on-call incident triage assistant. You will be given \
an alert. You do not have access to live service metrics — base your assessment only on the \
alert text.

Reply with ONLY a JSON object with these fields:
- "severity": one of {SEVERITY_LABELS}
- "category": one of {CATEGORY_LABELS}
- "service": the name of the affected service, or null if none is named
- "summary": a one-sentence summary of the incident
- "action": the single most appropriate next step, one of:
{ACTION_LINES}
- "confidence": a number from 0.0 to 1.0 indicating how confident you are in this decision

Reply with ONLY the JSON object — no markdown, no commentary."""

FINAL_ANSWER_PROMPT = "Now reply with ONLY the JSON object as specified."

FALLBACK_PROPOSAL: dict[str, Any] = {
    "output": {
        "severity": "medium",
        "category": "unknown",
        "summary": SUMMARY_TEMPLATES["unknown"],
    },
    "actions": ["escalate_incident"],
    "action": "escalate_incident",
    "confidence": 0.0,
}


def parse_incident_proposal(
    data: dict[str, Any], service_status: dict[str, Any] | None = None
) -> dict[str, Any]:
    if "category" not in data:
        raise KeyError("category")

    category = str(data.get("category") or "unknown").lower().replace(" ", "_")
    if category not in CATEGORY_TO_ACTION:
        category = "unknown"

    severity = str(data.get("severity") or "").lower()
    if severity not in SEVERITY_LABELS:
        severity = CATEGORY_TO_SEVERITY[category]

    summary = str(data.get("summary") or "") or SUMMARY_TEMPLATES[category]

    action = str(data.get("action") or "").lower().replace(" ", "_")
    if action not in ALLOWED_ACTIONS:
        action = CATEGORY_TO_ACTION[category]

    output: dict[str, Any] = {"severity": severity, "category": category, "summary": summary}
    if service := data.get("service"):
        output["service"] = str(service)
    if service_status is not None:
        output["service_status"] = service_status

    confidence = parse_confidence(data.get("confidence"))
    return {"output": output, "actions": [action], "action": action, "confidence": confidence}
