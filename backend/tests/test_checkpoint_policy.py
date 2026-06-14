"""Unit tests for the shared Level-5 checkpoint policy."""

from app.services.checkpoint_policy import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    evaluate,
    parse_confidence,
)


def test_parse_confidence_valid_value():
    assert parse_confidence(0.42) == 0.42


def test_parse_confidence_clamps_to_range():
    assert parse_confidence(1.5) == 1.0
    assert parse_confidence(-0.5) == 0.0


def test_parse_confidence_missing_falls_back_to_default():
    assert parse_confidence(None) == 1.0
    assert parse_confidence(None, default=0.0) == 0.0


def test_parse_confidence_non_numeric_falls_back_to_default():
    assert parse_confidence("not a number") == 1.0
    assert parse_confidence("not a number", default=0.0) == 0.0


def _evaluate(**overrides):
    defaults = {
        "action": "request_order_id",
        "output": {"intent": "shipping_issue", "order_id": "1234"},
        "confidence": 0.95,
        "retries": 0,
        "risky_actions": {"escalate_billing_review"},
        "required_fields": [],
        "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
    }
    defaults.update(overrides)
    return evaluate(**defaults)


def test_no_triggers_when_nothing_is_wrong():
    decision = _evaluate()

    assert decision.needs_approval is False
    assert decision.triggers == []
    assert decision.reason == ""
    assert decision.details == {"triggers": []}


def test_risky_action_triggers_approval():
    decision = _evaluate(action="escalate_billing_review")

    assert decision.needs_approval is True
    assert [t.kind for t in decision.triggers] == ["risky_action"]
    assert "escalate_billing_review" in decision.reason


def test_missing_fields_triggers_approval():
    decision = _evaluate(output={"intent": "shipping_issue"}, required_fields=["order_id"])

    assert decision.needs_approval is True
    assert [t.kind for t in decision.triggers] == ["missing_fields"]
    assert decision.details["triggers"][0]["missing_fields"] == ["order_id"]


def test_falsy_required_field_value_counts_as_missing():
    decision = _evaluate(
        output={"intent": "shipping_issue", "order_id": ""}, required_fields=["order_id"]
    )

    assert decision.needs_approval is True
    assert decision.triggers[0].kind == "missing_fields"


def test_low_confidence_triggers_approval():
    decision = _evaluate(confidence=0.3)

    assert decision.needs_approval is True
    assert [t.kind for t in decision.triggers] == ["low_confidence"]
    assert decision.details["triggers"][0]["confidence"] == 0.3
    assert decision.details["triggers"][0]["threshold"] == DEFAULT_CONFIDENCE_THRESHOLD


def test_confidence_at_threshold_does_not_trigger():
    decision = _evaluate(confidence=DEFAULT_CONFIDENCE_THRESHOLD)

    assert decision.needs_approval is False


def test_missing_confidence_does_not_trigger_low_confidence():
    decision = _evaluate(confidence=None)

    assert decision.needs_approval is False


def test_retries_trigger_conflicting_signals():
    decision = _evaluate(retries=2)

    assert decision.needs_approval is True
    assert [t.kind for t in decision.triggers] == ["conflicting_signals"]
    assert decision.details["triggers"][0]["retries"] == 2


def test_multiple_triggers_combine_in_order():
    decision = _evaluate(
        action="escalate_billing_review",
        output={"intent": "billing_issue"},
        required_fields=["order_id"],
        confidence=0.1,
        retries=1,
    )

    assert [t.kind for t in decision.triggers] == [
        "risky_action",
        "missing_fields",
        "low_confidence",
        "conflicting_signals",
    ]
    assert decision.needs_approval is True
    # reason joins all trigger reasons, so a human sees every cause at once.
    for trigger in decision.triggers:
        assert trigger.reason in decision.reason
