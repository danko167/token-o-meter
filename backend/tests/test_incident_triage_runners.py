"""Incident Triage coverage for the deterministic (L0/L1) runners — no
network calls."""

import pytest

from app.runners.rule_runner import RuleRunner
from app.runners.workflow_runner import WorkflowRunner
from app.schemas.scenario import Scenario

pytestmark = pytest.mark.anyio

DEPLOY_REGRESSION_ALERT = """\
ALERT: checkout-api p99 latency is 2150ms (SLO: 500ms), error rate is 8.2%
(normal: <0.5%). A deploy of checkout-api v2.14.0 went out 12 minutes ago.
CPU and memory usage are within normal ranges.
"""

MEMORY_LEAK_ALERT = """\
ALERT: recommendation-worker memory usage has climbed from 40% to 92% over
the last 6 hours and is still increasing. CPU usage and error rate are
within normal ranges. No deploys have been made to recommendation-worker in
the last 5 days.
"""

TRANSIENT_SPIKE_ALERT = """\
ALERT: auth-service had a 30-second latency spike to 1500ms at 02:14 UTC.
The service recovered by 02:15 and has been healthy since, with a 0% error
rate. No deploy has been made to auth-service in the last 30 days.
"""


def make_deploy_regression_scenario() -> Scenario:
    return Scenario(
        id="incident-deploy-regression",
        name="Incident Triage - Deploy Regression",
        family="incident_triage",
        input=DEPLOY_REGRESSION_ALERT,
    )


def make_memory_leak_scenario() -> Scenario:
    return Scenario(
        id="incident-memory-leak",
        name="Incident Triage - Memory Leak",
        family="incident_triage",
        input=MEMORY_LEAK_ALERT,
    )


def make_transient_spike_scenario() -> Scenario:
    return Scenario(
        id="incident-transient-spike",
        name="Incident Triage - Transient Spike",
        family="incident_triage",
        input=TRANSIENT_SPIKE_ALERT,
    )


async def test_rule_runner_classifies_deploy_regression():
    result = await RuleRunner().execute(
        make_deploy_regression_scenario(), "run-incident-rules-deploy"
    )

    assert result.output["category"] == "deployment_regression"
    assert result.output["severity"] == "high"
    assert result.actions == []
    assert result.confidence == 1.0


async def test_rule_runner_classifies_memory_leak_as_resource_exhaustion():
    result = await RuleRunner().execute(
        make_memory_leak_scenario(), "run-incident-rules-memory"
    )

    assert result.output["category"] == "resource_exhaustion"
    assert result.output["severity"] == "medium"
    assert result.actions == []
    assert result.confidence == 1.0


async def test_rule_runner_classifies_recovered_spike_as_transient():
    result = await RuleRunner().execute(
        make_transient_spike_scenario(), "run-incident-rules-transient"
    )

    assert result.output["category"] == "transient"
    assert result.output["severity"] == "low"
    assert result.actions == []
    assert result.confidence == 1.0


async def test_workflow_runner_recommends_rollback_for_deploy_regression():
    result = await WorkflowRunner().execute(
        make_deploy_regression_scenario(), "run-incident-workflow-deploy"
    )

    assert result.output["category"] == "deployment_regression"
    assert result.actions == ["rollback_deploy"]


async def test_workflow_runner_recommends_restart_for_memory_leak():
    result = await WorkflowRunner().execute(
        make_memory_leak_scenario(), "run-incident-workflow-memory"
    )

    assert result.output["category"] == "resource_exhaustion"
    assert result.actions == ["restart_service"]


async def test_workflow_runner_recommends_acknowledge_for_transient_spike():
    result = await WorkflowRunner().execute(
        make_transient_spike_scenario(), "run-incident-workflow-transient"
    )

    assert result.output["category"] == "transient"
    assert result.actions == ["acknowledge"]
