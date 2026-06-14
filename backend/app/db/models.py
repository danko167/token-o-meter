"""SQLAlchemy ORM model for persisted run history, plus conversion to/from
the RunResult Pydantic schema used everywhere else in the app."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.schemas.run import (
    Evaluation,
    EvaluationCheck,
    HumanEvaluation,
    Metrics,
    PendingApproval,
    RunResult,
    RunTrace,
)
from app.schemas.scenario import Scenario


class Base(DeclarativeBase):
    pass


class RunRecord(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String, index=True)
    scenario_family: Mapped[str | None] = mapped_column(String, default=None, index=True)
    runner: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    is_demo: Mapped[bool] = mapped_column(default=False, index=True)
    archived: Mapped[bool] = mapped_column(default=False, index=True)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, default=None)

    metrics_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    metrics_completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    metrics_estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_retries: Mapped[int] = mapped_column(Integer, default=0)
    metrics_tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, default=None)

    evaluation_score: Mapped[int | None] = mapped_column(Integer, default=None)
    evaluation_checks: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, default=None)

    human_evaluation_score: Mapped[int | None] = mapped_column(Integer, default=None)
    human_evaluation_useful: Mapped[bool | None] = mapped_column(default=None)
    human_evaluation_correct: Mapped[bool | None] = mapped_column(default=None)
    human_evaluation_comment: Mapped[str | None] = mapped_column(Text, default=None)
    human_evaluation_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )

    pending_approval_action: Mapped[str | None] = mapped_column(String, default=None)
    pending_approval_reason: Mapped[str | None] = mapped_column(Text, default=None)
    pending_approval_details: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    trace_events: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ScenarioRecord(Base):
    __tablename__ = "custom_scenarios"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    family: Mapped[str] = mapped_column(String, index=True)
    input: Mapped[str] = mapped_column(Text)
    expected: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    required_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    forbidden_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence_threshold: Mapped[float | None] = mapped_column(Float, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def record_from_scenario(scenario: Scenario) -> ScenarioRecord:
    return ScenarioRecord(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        family=scenario.family,
        input=scenario.input,
        expected=scenario.expected,
        required_fields=scenario.required_fields,
        forbidden_actions=scenario.forbidden_actions,
        confidence_threshold=scenario.confidence_threshold,
        created_at=datetime.now(UTC),
    )


def scenario_from_record(record: ScenarioRecord) -> Scenario:
    return Scenario(
        id=record.id,
        name=record.name,
        description=record.description,
        family=record.family,
        input=record.input,
        expected=record.expected,
        required_fields=record.required_fields,
        forbidden_actions=record.forbidden_actions,
        confidence_threshold=record.confidence_threshold,
        is_custom=True,
    )


def record_from_run_result(run: RunResult) -> RunRecord:
    evaluation = run.evaluation
    human_evaluation = run.human_evaluation
    pending = run.pending_approval
    return RunRecord(
        run_id=run.run_id,
        scenario_id=run.scenario_id,
        scenario_family=run.scenario_family,
        runner=run.runner,
        status=run.status,
        is_demo=run.is_demo,
        archived=run.archived,
        output=run.output,
        actions=run.actions,
        error=run.error,
        metrics_duration_ms=run.metrics.duration_ms,
        metrics_prompt_tokens=run.metrics.prompt_tokens,
        metrics_completion_tokens=run.metrics.completion_tokens,
        metrics_estimated_cost_usd=run.metrics.estimated_cost_usd,
        metrics_retries=run.metrics.retries,
        metrics_tool_calls=[call.model_dump() for call in run.metrics.tool_calls],
        evaluation_score=evaluation.score if evaluation else None,
        evaluation_checks=(
            [check.model_dump() for check in evaluation.checks] if evaluation else None
        ),
        human_evaluation_score=human_evaluation.score if human_evaluation else None,
        human_evaluation_useful=human_evaluation.useful if human_evaluation else None,
        human_evaluation_correct=human_evaluation.correct if human_evaluation else None,
        human_evaluation_comment=human_evaluation.comment if human_evaluation else None,
        human_evaluation_created_at=human_evaluation.created_at if human_evaluation else None,
        pending_approval_action=pending.action if pending else None,
        pending_approval_reason=pending.reason if pending else None,
        pending_approval_details=pending.details if pending else None,
        trace_events=[event.model_dump(mode="json") for event in run.trace.events],
        created_at=run.created_at,
    )


def run_result_from_record(record: RunRecord) -> RunResult:
    evaluation = None
    if record.evaluation_score is not None:
        evaluation = Evaluation(
            score=record.evaluation_score,
            checks=[EvaluationCheck(**check) for check in record.evaluation_checks or []],
        )

    pending_approval = None
    if record.pending_approval_action is not None:
        pending_approval = PendingApproval(
            action=record.pending_approval_action,
            reason=record.pending_approval_reason or "",
            details=record.pending_approval_details or {},
        )

    human_evaluation = None
    if record.human_evaluation_score is not None:
        human_created_at = record.human_evaluation_created_at or datetime.now(UTC)
        if human_created_at.tzinfo is None:
            human_created_at = human_created_at.replace(tzinfo=UTC)
        human_evaluation = HumanEvaluation(
            score=record.human_evaluation_score,
            useful=bool(record.human_evaluation_useful),
            correct=bool(record.human_evaluation_correct),
            comment=record.human_evaluation_comment or "",
            created_at=human_created_at,
        )

    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    return RunResult(
        run_id=record.run_id,
        scenario_id=record.scenario_id,
        scenario_family=record.scenario_family,
        runner=record.runner,
        status=record.status,
        is_demo=record.is_demo,
        archived=record.archived,
        output=record.output,
        actions=record.actions,
        error=record.error,
        metrics=Metrics(
            duration_ms=record.metrics_duration_ms,
            prompt_tokens=record.metrics_prompt_tokens,
            completion_tokens=record.metrics_completion_tokens,
            estimated_cost_usd=record.metrics_estimated_cost_usd,
            retries=record.metrics_retries,
            tool_calls=record.metrics_tool_calls or [],
        ),
        evaluation=evaluation,
        human_evaluation=human_evaluation,
        pending_approval=pending_approval,
        trace=RunTrace(events=record.trace_events or []),
        created_at=created_at,
    )
