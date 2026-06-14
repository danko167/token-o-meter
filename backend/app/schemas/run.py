from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.scenario import ScenarioFamily


class Metrics(BaseModel):
    duration_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    retries: int = 0
    tool_calls: list["ToolCallMetric"] = Field(default_factory=list)


class ToolCallMetric(BaseModel):
    name: str
    duration_ms: float = 0.0
    found: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationCheck(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class Evaluation(BaseModel):
    """Deterministic scoring of a runner's output against the scenario."""

    score: int = Field(ge=0, le=100)
    checks: list[EvaluationCheck] = Field(default_factory=list)


class PendingApproval(BaseModel):
    """A proposed action that a human must approve or reject before the run
    can complete (HumanCheckpointRunner, Level 5)."""

    action: str
    reason: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    """One observable step in a run timeline."""

    name: str
    kind: Literal[
        "request",
        "runner",
        "tool",
        "evaluation",
        "checkpoint",
        "decision",
        "error",
    ]
    timestamp: datetime
    duration_ms: float | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


class RunTrace(BaseModel):
    """Timeline and lightweight observability breakdown for a run."""

    events: list[TraceEvent] = Field(default_factory=list)


class HumanEvaluation(BaseModel):
    score: int = Field(ge=1, le=5)
    useful: bool
    correct: bool
    comment: str = ""
    created_at: datetime


class RunnerOutput(BaseModel):
    """What a runner produces before evaluation."""

    output: dict[str, Any] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)
    confidence: float | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    retries: int = 0
    pending_approval: PendingApproval | None = None
    trace_events: list[TraceEvent] = Field(default_factory=list)


class RunRequest(BaseModel):
    scenario_id: str
    runner: str
    llm_model: str | None = None


class RunDecisionRequest(BaseModel):
    """Human decision submitted for a run that is pending approval."""

    decision: Literal["approve", "reject"]


class RunIdsRequest(BaseModel):
    """A batch of run IDs for a bulk action (delete/archive/unarchive)."""

    run_ids: list[str] = Field(min_length=1)


class RunBulkActionResult(BaseModel):
    count: int = 0


class RunListPage(BaseModel):
    items: list["RunResult"]
    total: int
    page: int
    page_size: int


class RunUsageTotals(BaseModel):
    runs: int = 0
    demo_runs: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class RunModelUsage(RunUsageTotals):
    model: str


class RunRunnerModelUsage(RunModelUsage):
    runner: str


class RunRunnerUsage(RunUsageTotals):
    runner: str
    models: list[RunRunnerModelUsage] = Field(default_factory=list)


class RunUsageSummary(BaseModel):
    totals: RunUsageTotals
    by_model: list[RunModelUsage] = Field(default_factory=list)
    by_runner: list[RunRunnerUsage] = Field(default_factory=list)


class RunResult(BaseModel):
    run_id: str
    scenario_id: str
    scenario_family: ScenarioFamily | None = None
    runner: str
    status: Literal["succeeded", "failed", "pending_approval"]
    is_demo: bool = False
    archived: bool = False
    output: dict[str, Any] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)
    error: str | None = None
    metrics: Metrics
    evaluation: Evaluation | None = None
    human_evaluation: HumanEvaluation | None = None
    pending_approval: PendingApproval | None = None
    trace: RunTrace = Field(default_factory=RunTrace)
    created_at: datetime


class RunnerInfo(BaseModel):
    name: str
    level: int
    description: str


class HumanEvaluationRequest(BaseModel):
    score: int = Field(ge=1, le=5)
    useful: bool
    correct: bool
    comment: str = ""
