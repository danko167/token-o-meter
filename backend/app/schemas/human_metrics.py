from pydantic import BaseModel, Field


class HumanMetricsResult(BaseModel):
    scenario_id: str | None = None
    total_runs: int = 0
    checkpointed_runs: int = 0
    approved_runs: int = 0
    rejected_runs: int = 0
    pending_runs: int = 0
    escalated_runs: int = 0
    checkpoint_rate: float = Field(ge=0.0, le=1.0)
    approval_rate: float = Field(ge=0.0, le=1.0)
    rejection_rate: float = Field(ge=0.0, le=1.0)
    escalation_rate: float = Field(ge=0.0, le=1.0)
    intervention_rate_by_runner: dict[str, float] = Field(default_factory=dict)
    totals_by_runner: dict[str, int] = Field(default_factory=dict)
