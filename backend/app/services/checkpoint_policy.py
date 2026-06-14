"""Reusable Level-5 checkpoint policy.

Generalizes "should this run pause for human approval, and why?" across all
scenario families. A run is flagged for approval if any of the following
triggers fire:

- ``risky_action``: the proposed action is in the family's high-impact set.
- ``missing_fields``: the proposed output is missing a scenario-required field.
- ``low_confidence``: the model's self-reported confidence is below threshold.
- ``conflicting_signals``: the model needed retries to produce a valid response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Default confidence threshold below which a run pauses for review, used
#: when a scenario doesn't specify its own.
DEFAULT_CONFIDENCE_THRESHOLD = 0.7


def parse_confidence(value: Any, default: float = 1.0) -> float:
    """Clamp a model-reported confidence value to [0, 1].

    Falls back to `default` if `value` is missing or not a number.
    """
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, confidence))


@dataclass
class CheckpointTrigger:
    kind: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckpointDecision:
    triggers: list[CheckpointTrigger]

    @property
    def needs_approval(self) -> bool:
        return bool(self.triggers)

    @property
    def reason(self) -> str:
        return " ".join(trigger.reason for trigger in self.triggers)

    @property
    def details(self) -> dict[str, Any]:
        return {
            "triggers": [
                {"kind": trigger.kind, "reason": trigger.reason, **trigger.details}
                for trigger in self.triggers
            ]
        }


def evaluate(
    *,
    action: str | None,
    output: dict[str, Any],
    confidence: float | None,
    retries: int,
    risky_actions: set[str],
    required_fields: list[str],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> CheckpointDecision:
    """Evaluate all checkpoint triggers for a proposed action."""
    triggers: list[CheckpointTrigger] = []

    if action in risky_actions:
        triggers.append(
            CheckpointTrigger(
                kind="risky_action",
                reason=f"'{action}' is a high-impact action that requires human review.",
                details={"action": action},
            )
        )

    missing_fields = [name for name in required_fields if not output.get(name)]
    if missing_fields:
        triggers.append(
            CheckpointTrigger(
                kind="missing_fields",
                reason=f"Missing required field(s): {', '.join(missing_fields)}.",
                details={"missing_fields": missing_fields},
            )
        )

    if confidence is not None and confidence < confidence_threshold:
        triggers.append(
            CheckpointTrigger(
                kind="low_confidence",
                reason=(
                    f"Model confidence ({confidence:.2f}) is below the "
                    f"threshold ({confidence_threshold:.2f})."
                ),
                details={"confidence": confidence, "threshold": confidence_threshold},
            )
        )

    if retries > 0:
        retry_word = "retry" if retries == 1 else "retries"
        triggers.append(
            CheckpointTrigger(
                kind="conflicting_signals",
                reason=(
                    f"The model needed {retries} {retry_word} to produce a valid "
                    "response, suggesting conflicting or unclear signals."
                ),
                details={"retries": retries},
            )
        )

    return CheckpointDecision(triggers=triggers)
