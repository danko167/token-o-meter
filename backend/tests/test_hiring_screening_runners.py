"""Hiring Screening coverage for the deterministic (L0/L1) runners — no
network calls."""

import pytest

from app.runners.rule_runner import RuleRunner
from app.runners.workflow_runner import WorkflowRunner
from app.schemas.scenario import Scenario

pytestmark = pytest.mark.anyio

STRONG_MATCH_RESUME = """\
Role: senior-backend-engineer

Resume:
Backend engineer with 7 years of professional experience building and
operating production services. Core stack: Python, AWS, PostgreSQL, and
Kubernetes. Regularly participates in the on-call rotation, responding to
incidents and leading postmortems. Has led migrations of high-traffic
services to Kubernetes and tuned PostgreSQL for heavy read workloads.
"""

MISSING_SKILL_RESUME = """\
Role: senior-backend-engineer

Resume:
Backend engineer with 6 years of professional experience. Core stack:
Python, MySQL, Docker, and Jenkins. Built and maintained internal tooling
and CI/CD pipelines for a mid-sized engineering team, with a focus on
on-premises infrastructure and traditional relational databases.
"""

INCOMPLETE_RESUME = """\
Role: senior-backend-engineer

Resume:
Python developer who has worked on a variety of backend projects.
Comfortable writing clean, well-tested code and collaborating with
cross-functional teams.
"""


def make_strong_match_scenario() -> Scenario:
    return Scenario(
        id="screening-strong-match",
        name="Hiring Screening - Strong Match",
        family="hiring_screening",
        input=STRONG_MATCH_RESUME,
    )


def make_missing_skill_scenario() -> Scenario:
    return Scenario(
        id="screening-missing-required-skill",
        name="Hiring Screening - Missing Required Skills",
        family="hiring_screening",
        input=MISSING_SKILL_RESUME,
    )


def make_incomplete_resume_scenario() -> Scenario:
    return Scenario(
        id="screening-incomplete-resume",
        name="Hiring Screening - Incomplete Resume",
        family="hiring_screening",
        input=INCOMPLETE_RESUME,
    )


async def test_rule_runner_advances_strong_match():
    result = await RuleRunner().execute(
        make_strong_match_scenario(), "run-hiring-rules-strong-match"
    )

    assert result.output["decision"] == "advance_to_interview"
    assert result.output["missing_requirements"] == []
    assert result.actions == []
    assert result.confidence == 1.0


async def test_rule_runner_rejects_missing_skills():
    result = await RuleRunner().execute(
        make_missing_skill_scenario(), "run-hiring-rules-missing-skill"
    )

    assert result.output["decision"] == "reject"
    assert len(result.output["missing_requirements"]) >= 2
    assert result.actions == []
    assert result.confidence == 1.0


async def test_rule_runner_requests_more_info_for_incomplete_resume():
    result = await RuleRunner().execute(
        make_incomplete_resume_scenario(), "run-hiring-rules-incomplete"
    )

    assert result.output["decision"] == "request_more_info"
    assert result.actions == []
    assert result.confidence == 1.0


async def test_workflow_runner_advances_strong_match():
    result = await WorkflowRunner().execute(
        make_strong_match_scenario(), "run-hiring-workflow-strong-match"
    )

    assert result.output["decision"] == "advance_to_interview"
    assert result.actions == ["advance_to_interview"]


async def test_workflow_runner_rejects_missing_skills():
    result = await WorkflowRunner().execute(
        make_missing_skill_scenario(), "run-hiring-workflow-missing-skill"
    )

    assert result.output["decision"] == "reject"
    assert result.actions == ["reject"]


async def test_workflow_runner_requests_more_info_for_incomplete_resume():
    result = await WorkflowRunner().execute(
        make_incomplete_resume_scenario(), "run-hiring-workflow-incomplete"
    )

    assert result.output["decision"] == "request_more_info"
    assert result.actions == ["request_more_info"]
