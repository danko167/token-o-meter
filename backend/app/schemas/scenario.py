from typing import Any, Literal

from pydantic import BaseModel, Field

ScenarioFamily = Literal[
    "customer_support",
    "policy_qa",
    "git_diff_review",
    "incident_triage",
    "hiring_screening",
]


class Scenario(BaseModel):
    """A benchmark scenario: one input plus the expectations used to score
    whatever runner is thrown at it. Loaded from YAML files in scenarios/."""

    id: str
    name: str
    description: str = ""
    input: str
    family: ScenarioFamily = "customer_support"
    expected: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    is_custom: bool = False
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class ScenarioSummary(BaseModel):
    id: str
    name: str
    description: str = ""
    family: ScenarioFamily = "customer_support"
    is_custom: bool = False


class ScenarioCreate(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    input: str
    family: ScenarioFamily
    expected: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
