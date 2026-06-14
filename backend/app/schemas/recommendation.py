from typing import Literal

from pydantic import BaseModel, Field


class RunnerRecommendationStats(BaseModel):
    runner: str
    level: int
    total_runs: int
    succeeded_runs: int
    failed_runs: int
    pending_runs: int
    success_rate: float = Field(ge=0.0, le=1.0)
    average_score: float | None = None
    average_duration_ms: float | None = None
    average_cost_usd: float | None = None
    average_retries: float | None = None
    checkpoint_rate: float = Field(ge=0.0, le=1.0)
    reliable: bool
    reasons: list[str] = Field(default_factory=list)


class StrategySimulation(BaseModel):
    sample_size: int = 0
    primary_success_rate: float = Field(ge=0.0, le=1.0)
    fallback_success_rate: float = Field(ge=0.0, le=1.0)
    projected_primary_handled_rate: float = Field(ge=0.0, le=1.0)
    projected_fallback_handled_rate: float = Field(ge=0.0, le=1.0)
    projected_human_intervention_rate: float = Field(ge=0.0, le=1.0)
    projected_success_rate: float = Field(ge=0.0, le=1.0)
    projected_average_cost_usd: float | None = None
    projected_average_duration_ms: float | None = None


class CounterfactualExplanation(BaseModel):
    runner: str
    outcome: Literal[
        "recommended",
        "primary",
        "fallback",
        "needs_data",
        "not_reliable",
        "higher_complexity",
        "superseded",
    ]
    summary: str
    reasons: list[str] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    scenario_id: str
    recommended_runner: str | None
    recommended_level: int | None
    strategy: str = "single_runner"
    primary_runner: str | None = None
    fallback_runner: str | None = None
    operational_complexity: int = Field(default=1, ge=1, le=5)
    simulation: StrategySimulation | None = None
    confidence: float
    summary: str
    reasoning: list[str] = Field(default_factory=list)
    counterfactuals: list[CounterfactualExplanation] = Field(default_factory=list)
    runners: list[RunnerRecommendationStats] = Field(default_factory=list)
