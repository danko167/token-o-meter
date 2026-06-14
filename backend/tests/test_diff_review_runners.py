"""Git Diff Review coverage for the deterministic (L0/L1) runners — no
network calls."""

import pytest

from app.runners.rule_runner import RuleRunner
from app.runners.workflow_runner import WorkflowRunner
from app.schemas.scenario import Scenario

pytestmark = pytest.mark.anyio

SECRET_DIFF = """\
diff --git a/app/config.py b/app/config.py
index 4a3f2c1..8b9d3e2 100644
--- a/app/config.py
+++ b/app/config.py
@@ -1,2 +1,3 @@
 DEBUG = False
 DATABASE_URL = "sqlite:///app.db"
+OPENROUTER_API_KEY = "sk-live-abcdef1234567890"
"""

MISSING_TEST_DIFF = """\
diff --git a/app/payments.py b/app/payments.py
index 1a2b3c4..5d6e7f8 100644
--- a/app/payments.py
+++ b/app/payments.py
@@ -1,2 +1,6 @@
 def calculate_total(price: float, quantity: int) -> float:
     return price * quantity
+
+
+def apply_discount(price: float, percent: float) -> float:
+    return price * (1 - percent / 100)
"""


def make_secret_diff_scenario() -> Scenario:
    return Scenario(
        id="diff-hardcoded-secret",
        name="Git Diff Review - Hardcoded Secret",
        family="git_diff_review",
        input=SECRET_DIFF,
    )


def make_missing_test_diff_scenario() -> Scenario:
    return Scenario(
        id="diff-missing-test-coverage",
        name="Git Diff Review - Missing Test Coverage",
        family="git_diff_review",
        input=MISSING_TEST_DIFF,
    )


async def test_rule_runner_flags_hardcoded_secret():
    result = await RuleRunner().execute(make_secret_diff_scenario(), "run-diff-rules-secret")

    assert result.output["verdict"] == "request_changes"
    categories = {f["category"] for f in result.output["findings"]}
    assert "hardcoded_secret" in categories
    assert result.actions == []
    assert result.confidence == 1.0


async def test_rule_runner_flags_missing_tests_as_comment():
    result = await RuleRunner().execute(
        make_missing_test_diff_scenario(), "run-diff-rules-tests"
    )

    assert result.output["verdict"] == "comment"
    categories = {f["category"] for f in result.output["findings"]}
    assert "missing_tests" in categories
    assert result.actions == []


async def test_workflow_runner_categorizes_secret_as_security():
    result = await WorkflowRunner().execute(
        make_secret_diff_scenario(), "run-diff-workflow-secret"
    )

    assert result.output["category"] == "security"
    assert result.output["verdict"] == "request_changes"
    assert result.actions == ["request_changes"]


async def test_workflow_runner_categorizes_missing_tests_as_testing():
    result = await WorkflowRunner().execute(
        make_missing_test_diff_scenario(), "run-diff-workflow-tests"
    )

    assert result.output["category"] == "testing"
    assert result.output["verdict"] == "comment"
    assert result.actions == ["comment_on_pr"]
