"""Executes a runner against a scenario, collects metrics, evaluates the
output, and stores the result."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, delete, func, select, update
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.migrations import run_migrations
from app.db.models import RunRecord, record_from_run_result, run_result_from_record
from app.runners import hiring_screening, incident_triage
from app.runners.base import RunnerRegistry
from app.schemas.run import Metrics, RunnerOutput, RunResult, RunTrace, ToolCallMetric, TraceEvent
from app.schemas.run import RunModelUsage, RunRunnerModelUsage, RunRunnerUsage, RunUsageSummary
from app.schemas.run import RunUsageTotals
from app.schemas.scenario import Scenario
from app.services.evaluation import evaluate, evaluate_with_judge
from app.services.llm_client import LLMClient, use_llm_model
from app.services.llm_models import (
    OPENAI_PROVIDER,
    OPENROUTER_PROVIDER,
    model_provider,
    provider_display_name,
)
from app.services.scenario_store import ScenarioStore

logger = logging.getLogger(__name__)

LLM_BACKED_RUNNERS = {"llm", "tool", "agent", "human_checkpoint"}
PROVIDER_RATE_LIMIT_MESSAGE = (
    "LLM provider rate limit exceeded. OpenRouter rejected the request because "
    "the selected model quota is exhausted. Try again after the reset window, "
    "choose another configured model, or add provider credits."
)
PROVIDER_RATE_LIMIT_COOLDOWN = timedelta(minutes=5)


def provider_rate_limit_message(provider: str | None = None) -> str:
    if provider == OPENAI_PROVIDER:
        return (
            "LLM provider rate limit exceeded. OpenAI rejected the request because "
            "the selected model quota or rate limit is exhausted. Try again after "
            "the reset window, choose another configured model, or add provider credits."
        )
    if provider == OPENROUTER_PROVIDER:
        return PROVIDER_RATE_LIMIT_MESSAGE
    return (
        "LLM provider rate limit exceeded. The selected model provider rejected "
        "the request because quota or rate limit is exhausted. Try again after "
        "the reset window, choose another configured model, or add provider credits."
    )


class RunStore:
    """SQLAlchemy/SQLite-backed run history, newest first."""

    def __init__(self, database_path: Path, migrate: bool = True) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        if migrate:
            run_migrations(self._database_path)
        self._engine = create_engine(
            f"sqlite:///{self._database_path}",
            connect_args={"check_same_thread": False},
        )
        self._session_factory = sessionmaker(bind=self._engine)

    def add(self, run: RunResult) -> None:
        with self._session_factory() as session:
            session.merge(record_from_run_result(run))
            session.commit()

    def get(self, run_id: str) -> RunResult | None:
        with self._session_factory() as session:
            record = session.get(RunRecord, run_id)
            return run_result_from_record(record) if record is not None else None

    def list(
        self,
        include_archived: bool = False,
        scenario_id: str | None = None,
        scenario_family: str | None = None,
    ) -> list[RunResult]:
        with self._session_factory() as session:
            query = select(RunRecord).order_by(RunRecord.created_at.desc())
            if not include_archived:
                query = query.where(RunRecord.archived.is_(False))
            if scenario_id is not None:
                query = query.where(RunRecord.scenario_id == scenario_id)
            if scenario_family is not None:
                query = query.where(RunRecord.scenario_family == scenario_family)
            records = session.scalars(query).all()
            return [run_result_from_record(record) for record in records]

    def list_page(
        self,
        include_archived: bool = False,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[RunResult], int]:
        offset = (page - 1) * page_size
        with self._session_factory() as session:
            filters = []
            if not include_archived:
                filters.append(RunRecord.archived.is_(False))

            total_query = select(func.count()).select_from(RunRecord)
            page_query = (
                select(RunRecord)
                .order_by(RunRecord.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            if filters:
                total_query = total_query.where(*filters)
                page_query = page_query.where(*filters)

            total = int(session.scalar(total_query) or 0)
            records = session.scalars(page_query).all()
            return [run_result_from_record(record) for record in records], total

    def latest_by_runner(
        self,
        scenario_id: str,
        include_archived: bool = False,
    ) -> list[RunResult]:
        with self._session_factory() as session:
            query = (
                select(RunRecord)
                .where(RunRecord.scenario_id == scenario_id)
                .order_by(RunRecord.created_at.desc())
            )
            if not include_archived:
                query = query.where(RunRecord.archived.is_(False))

            records = session.scalars(query).all()
            latest: dict[str, RunRecord] = {}
            for record in records:
                if record.runner not in latest:
                    latest[record.runner] = record
            return [run_result_from_record(record) for record in latest.values()]

    def usage_summary(self, include_archived: bool = True) -> RunUsageSummary:
        with self._session_factory() as session:
            query = select(RunRecord)
            if not include_archived:
                query = query.where(RunRecord.archived.is_(False))
            records = session.scalars(query).all()

        totals = _empty_usage_totals()
        by_model: dict[str, RunModelUsage] = {}
        by_runner: dict[str, RunRunnerUsage] = {}
        by_runner_model: dict[tuple[str, str], RunRunnerModelUsage] = {}

        for record in records:
            _add_record_usage(totals, record)
            if not _has_token_spend(record):
                continue

            model = _record_model(record)
            model_usage = by_model.setdefault(model, RunModelUsage(model=model))
            _add_record_usage(model_usage, record)

            runner_usage = by_runner.setdefault(
                record.runner,
                RunRunnerUsage(runner=record.runner),
            )
            _add_record_usage(runner_usage, record)

            runner_model_key = (record.runner, model)
            runner_model_usage = by_runner_model.setdefault(
                runner_model_key,
                RunRunnerModelUsage(runner=record.runner, model=model),
            )
            _add_record_usage(runner_model_usage, record)

        for runner_model_usage in by_runner_model.values():
            by_runner[runner_model_usage.runner].models.append(runner_model_usage)

        for runner_usage in by_runner.values():
            runner_usage.models.sort(
                key=lambda item: (
                    -item.estimated_cost_usd,
                    item.model,
                )
            )

        return RunUsageSummary(
            totals=totals,
            by_model=sorted(
                by_model.values(),
                key=lambda item: (
                    -item.estimated_cost_usd,
                    -(item.input_tokens + item.output_tokens),
                    item.model,
                ),
            ),
            by_runner=sorted(
                by_runner.values(),
                key=lambda item: (
                    -item.estimated_cost_usd,
                    item.runner,
                ),
            ),
        )

    def delete_demo_runs(self) -> int:
        with self._session_factory() as session:
            result = session.execute(delete(RunRecord).where(RunRecord.is_demo.is_(True)))
            session.commit()
            return int(result.rowcount or 0)

    def delete(self, run_ids: list[str]) -> int:
        with self._session_factory() as session:
            result = session.execute(delete(RunRecord).where(RunRecord.run_id.in_(run_ids)))
            session.commit()
            return int(result.rowcount or 0)

    def has_runs_for_scenario(self, scenario_id: str) -> bool:
        with self._session_factory() as session:
            return (
                session.execute(
                    select(RunRecord.run_id)
                    .where(RunRecord.scenario_id == scenario_id)
                    .limit(1)
                ).first()
                is not None
            )

    def has_pending_runs_for_scenario(self, scenario_id: str) -> bool:
        with self._session_factory() as session:
            return (
                session.execute(
                    select(RunRecord.run_id)
                    .where(
                        RunRecord.scenario_id == scenario_id,
                        RunRecord.status == "pending_approval",
                    )
                    .limit(1)
                ).first()
                is not None
            )

    def set_archived(self, run_ids: list[str], archived: bool) -> int:
        with self._session_factory() as session:
            result = session.execute(
                update(RunRecord).where(RunRecord.run_id.in_(run_ids)).values(archived=archived)
            )
            session.commit()
            return int(result.rowcount or 0)


def _empty_usage_totals() -> RunUsageTotals:
    return RunUsageTotals(
        runs=0,
        demo_runs=0,
        input_tokens=0,
        output_tokens=0,
        estimated_cost_usd=0.0,
    )


def _add_record_usage(target: RunUsageTotals, record: RunRecord) -> None:
    target.runs += 1
    target.demo_runs += 1 if record.is_demo else 0
    target.input_tokens += record.metrics_prompt_tokens
    target.output_tokens += record.metrics_completion_tokens
    target.estimated_cost_usd += record.metrics_estimated_cost_usd


def _has_token_spend(record: RunRecord) -> bool:
    return (
        record.metrics_prompt_tokens > 0
        or record.metrics_completion_tokens > 0
        or record.metrics_estimated_cost_usd > 0
    )


def _record_model(record: RunRecord) -> str:
    for event in record.trace_events or []:
        details = event.get("details") if isinstance(event, dict) else None
        model = details.get("llm_model") if isinstance(details, dict) else None
        if isinstance(model, str) and model.strip():
            return model
    return "Default model (not recorded)"


class RunNotFoundError(KeyError):
    pass


class RunNotResumableError(RuntimeError):
    """Raised when trying to resume a run that isn't pending approval."""


class ExecutionService:
    def __init__(
        self,
        registry: RunnerRegistry,
        store: RunStore,
        judge_client: LLMClient | None = None,
    ) -> None:
        self._registry = registry
        self._store = store
        self._judge_client = judge_client
        self._provider_rate_limited_until: dict[str, datetime] = {}

    async def run(
        self,
        scenario: Scenario,
        runner_name: str,
        llm_model: str | None = None,
        is_demo: bool = False,
    ) -> RunResult:
        runner = self._registry.get(runner_name)
        run_id = uuid.uuid4().hex[:12]
        provider = self._llm_provider_for(llm_model)
        if runner_name in LLM_BACKED_RUNNERS and self._provider_rate_limited(provider):
            return self._record_provider_rate_limited_run(
                scenario,
                runner_name,
                run_id,
                is_demo,
                provider,
            )

        logger.info(
            "run started: run_id=%s scenario=%s runner=%s", run_id, scenario.id, runner_name
        )

        created_at = datetime.now(UTC)
        trace_events = [
            TraceEvent(
                name="Request received",
                kind="request",
                timestamp=created_at,
                details={
                    "scenario_id": scenario.id,
                    "runner": runner_name,
                    **({"llm_model": llm_model} if llm_model else {}),
                },
            )
        ]
        start = time.perf_counter()
        try:
            with use_llm_model(llm_model):
                output = await runner.execute(scenario, run_id)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            error_message = clean_runner_error(exc, provider)
            if is_provider_rate_limit_exception(exc):
                self._provider_rate_limited_until[provider] = (
                    datetime.now(UTC) + PROVIDER_RATE_LIMIT_COOLDOWN
                )
                logger.warning(
                    "run failed: run_id=%s scenario=%s runner=%s duration_ms=%.1f error=%s",
                    run_id,
                    scenario.id,
                    runner_name,
                    duration_ms,
                    error_message,
                )
            else:
                logger.exception(
                    "run failed: run_id=%s scenario=%s runner=%s duration_ms=%.1f error=%s",
                    run_id,
                    scenario.id,
                    runner_name,
                    duration_ms,
                    error_message,
                )
            trace_events.append(
                TraceEvent(
                    name="Runner failed",
                    kind="error",
                    timestamp=datetime.now(UTC),
                    duration_ms=round(duration_ms, 1),
                    details={"error": error_message},
                )
            )
            result = RunResult(
                run_id=run_id,
                scenario_id=scenario.id,
                scenario_family=scenario.family,
                runner=runner_name,
                status="failed",
                is_demo=is_demo,
                error=error_message,
                metrics=Metrics(duration_ms=round(duration_ms, 1)),
                trace=RunTrace(events=trace_events),
                created_at=created_at,
            )
            self._store.add(result)
            return result

        duration_ms = (time.perf_counter() - start) * 1000
        trace_events.extend(_events_from_output(output, duration_ms))

        if output.pending_approval is not None:
            trace_events.append(
                TraceEvent(
                    name="Human checkpoint",
                    kind="checkpoint",
                    timestamp=datetime.now(UTC),
                    details={
                        "action": output.pending_approval.action,
                        "reason": output.pending_approval.reason,
                        "triggers": output.pending_approval.details.get("triggers", []),
                    },
                )
            )
            result = RunResult(
                run_id=run_id,
                scenario_id=scenario.id,
                scenario_family=scenario.family,
                runner=runner_name,
                status="pending_approval",
                is_demo=is_demo,
                output=output.output,
                actions=output.actions,
                metrics=Metrics(
                    duration_ms=round(duration_ms, 1),
                    prompt_tokens=output.prompt_tokens,
                    completion_tokens=output.completion_tokens,
                    estimated_cost_usd=output.estimated_cost_usd,
                    retries=output.retries,
                    tool_calls=_tool_metrics_from_output(output),
                ),
                pending_approval=output.pending_approval,
                trace=RunTrace(events=trace_events),
                created_at=created_at,
            )
            self._store.add(result)
            logger.info(
                "run pending approval: run_id=%s scenario=%s runner=%s action=%s "
                "duration_ms=%.1f",
                run_id,
                scenario.id,
                runner_name,
                output.pending_approval.action,
                duration_ms,
            )
            return result

        evaluation = await evaluate_with_judge(scenario, output, self._judge_client)
        trace_events.append(
            TraceEvent(
                name="Evaluation",
                kind="evaluation",
                timestamp=datetime.now(UTC),
                details={
                    "score": evaluation.score,
                    "checks": [check.model_dump() for check in evaluation.checks],
                    "llm_judge_enabled": self._judge_client is not None,
                },
            )
        )
        result = RunResult(
            run_id=run_id,
            scenario_id=scenario.id,
            scenario_family=scenario.family,
            runner=runner_name,
            status="succeeded",
            is_demo=is_demo,
            output=output.output,
            actions=output.actions,
            metrics=Metrics(
                duration_ms=round(duration_ms, 1),
                prompt_tokens=output.prompt_tokens,
                completion_tokens=output.completion_tokens,
                estimated_cost_usd=output.estimated_cost_usd,
                retries=output.retries,
                tool_calls=_tool_metrics_from_output(output),
            ),
            evaluation=evaluation,
            trace=RunTrace(events=trace_events),
            created_at=created_at,
        )
        self._store.add(result)
        logger.info(
            "run succeeded: run_id=%s scenario=%s runner=%s score=%s duration_ms=%.1f "
            "cost_usd=%.6f",
            run_id,
            scenario.id,
            runner_name,
            result.evaluation.score if result.evaluation else "n/a",
            duration_ms,
            result.metrics.estimated_cost_usd,
        )
        return result

    def _llm_provider_for(self, llm_model: str | None) -> str:
        settings = get_settings()
        model = llm_model or settings.llm_model
        return model_provider(model, settings) or model

    def _provider_rate_limited(self, provider: str) -> bool:
        return (
            provider in self._provider_rate_limited_until
            and datetime.now(UTC) < self._provider_rate_limited_until[provider]
        )

    def _record_provider_rate_limited_run(
        self,
        scenario: Scenario,
        runner_name: str,
        run_id: str,
        is_demo: bool,
        provider: str,
    ) -> RunResult:
        created_at = datetime.now(UTC)
        error_message = provider_rate_limit_message(provider)
        provider_name = (
            provider_display_name(provider)
            if provider in {OPENAI_PROVIDER, OPENROUTER_PROVIDER}
            else provider
        )
        logger.info(
            "run skipped because provider is rate limited: run_id=%s scenario=%s "
            "runner=%s provider=%s",
            run_id,
            scenario.id,
            runner_name,
            provider_name,
        )
        result = RunResult(
            run_id=run_id,
            scenario_id=scenario.id,
            scenario_family=scenario.family,
            runner=runner_name,
            status="failed",
            is_demo=is_demo,
            error=f"Skipped: {error_message}",
            metrics=Metrics(),
            trace=RunTrace(
                events=[
                    TraceEvent(
                        name="Runner skipped",
                        kind="error",
                        timestamp=created_at,
                        details={"error": error_message, "provider": provider_name},
                    )
                ]
            ),
            created_at=created_at,
        )
        self._store.add(result)
        return result

    async def resume(
        self, run_id: str, decision: str, scenarios: ScenarioStore
    ) -> RunResult:
        """Submit a human decision for a run that is `pending_approval`."""
        run = self._store.get(run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if run.status != "pending_approval":
            raise RunNotResumableError(
                f"run {run_id} is not pending approval (status={run.status})"
            )

        runner = self._registry.get(run.runner)
        scenario = scenarios.get(run.scenario_id)
        logger.info("run resume started: run_id=%s decision=%s", run_id, decision)

        start = time.perf_counter()
        try:
            output = await runner.resume(run_id, decision)
        except Exception as exc:
            fallback = self._resume_from_pending_record(run, scenario, decision)
            if fallback is not None:
                logger.warning(
                    "run %s resumed from persisted pending approval after checkpoint miss: %s",
                    run_id,
                    exc,
                )
                self._store.add(fallback)
                return fallback

            duration_ms = (time.perf_counter() - start) * 1000
            error_message = clean_runner_error(exc)
            if is_provider_rate_limit_exception(exc):
                logger.warning(
                    "run resume failed: run_id=%s decision=%s duration_ms=%.1f error=%s",
                    run_id,
                    decision,
                    duration_ms,
                    error_message,
                )
            else:
                logger.exception(
                    "run resume failed: run_id=%s decision=%s duration_ms=%.1f error=%s",
                    run_id,
                    decision,
                    duration_ms,
                    error_message,
                )
            result = run.model_copy(
                update={
                    "status": "failed",
                    "error": error_message,
                    "pending_approval": None,
                    "metrics": run.metrics.model_copy(
                        update={"duration_ms": round(run.metrics.duration_ms + duration_ms, 1)}
                    ),
                }
            )
            self._store.add(result)
            return result

        duration_ms = (time.perf_counter() - start) * 1000
        trace_events = [
            *run.trace.events,
            TraceEvent(
                name="Human decision",
                kind="decision",
                timestamp=datetime.now(UTC),
                duration_ms=round(duration_ms, 1),
                details={"decision": decision},
            ),
            *_events_from_output(output, duration_ms),
        ]
        evaluation = await evaluate_with_judge(scenario, output, self._judge_client)
        trace_events.append(
            TraceEvent(
                name="Evaluation",
                kind="evaluation",
                timestamp=datetime.now(UTC),
                details={
                    "score": evaluation.score,
                    "checks": [check.model_dump() for check in evaluation.checks],
                    "llm_judge_enabled": self._judge_client is not None,
                },
            )
        )
        result = RunResult(
            run_id=run_id,
            scenario_id=run.scenario_id,
            scenario_family=run.scenario_family or scenario.family,
            runner=run.runner,
            status="succeeded",
            is_demo=run.is_demo,
            output=output.output,
            actions=output.actions,
            metrics=Metrics(
                duration_ms=round(run.metrics.duration_ms + duration_ms, 1),
                prompt_tokens=output.prompt_tokens,
                completion_tokens=output.completion_tokens,
                estimated_cost_usd=output.estimated_cost_usd,
                retries=output.retries,
                tool_calls=_tool_metrics_from_output(output),
            ),
            evaluation=evaluation,
            trace=RunTrace(events=trace_events),
            created_at=run.created_at,
        )
        self._store.add(result)
        logger.info(
            "run resumed and succeeded: run_id=%s decision=%s score=%s duration_ms=%.1f",
            run_id,
            decision,
            result.evaluation.score if result.evaluation else "n/a",
            duration_ms,
        )
        return result

    def _resume_from_pending_record(
        self, run: RunResult, scenario: Scenario, decision: str
    ) -> RunResult | None:
        """Finalize from the persisted pending approval when graph memory is gone.

        LangGraph checkpoints are in-memory in this install, so a process restart
        loses the graph thread. The pending RunResult still contains the proposed
        action/output, which is enough to make approve/reject durable.
        """
        if run.pending_approval is None:
            return None

        output = dict(run.pending_approval.details or run.output)
        output["approval_decision"] = decision

        proposed_action = run.pending_approval.action
        if decision == "approve":
            actions = [proposed_action] if proposed_action else []
        else:
            if proposed_action:
                output["proposed_action"] = proposed_action
            reject_actions = {
                "policy_qa": "escalate_policy_review",
                "incident_triage": incident_triage.REJECT_ACTION,
                "hiring_screening": hiring_screening.REJECT_ACTION,
            }
            actions = [reject_actions.get(scenario.family, "escalate_general_review")]

        runner_output = RunnerOutput(output=output, actions=actions)
        evaluation = evaluate(scenario, runner_output)
        result = RunResult(
            run_id=run.run_id,
            scenario_id=run.scenario_id,
            scenario_family=run.scenario_family or scenario.family,
            runner=run.runner,
            status="succeeded",
            is_demo=run.is_demo,
            output=output,
            actions=actions,
            metrics=run.metrics,
            evaluation=evaluation,
            trace=RunTrace(
                events=[
                    *run.trace.events,
                    TraceEvent(
                        name="Human decision",
                        kind="decision",
                        timestamp=datetime.now(UTC),
                        details={"decision": decision, "resumed_from_persisted_record": True},
                    ),
                    TraceEvent(
                        name="Evaluation",
                        kind="evaluation",
                        timestamp=datetime.now(UTC),
                        details={
                            "score": evaluation.score,
                            "checks": [check.model_dump() for check in evaluation.checks],
                        },
                    ),
                ]
            ),
            created_at=run.created_at,
        )
        return result


def _events_from_output(output: RunnerOutput, duration_ms: float) -> list[TraceEvent]:
    events = [
        *output.trace_events,
        TraceEvent(
            name="Runner execution",
            kind="runner",
            timestamp=datetime.now(UTC),
            duration_ms=round(duration_ms, 1),
            prompt_tokens=output.prompt_tokens,
            completion_tokens=output.completion_tokens,
            estimated_cost_usd=output.estimated_cost_usd,
            details={
                "actions": output.actions,
                "confidence": output.confidence,
                "retries": output.retries,
            },
        )
    ]

    for call in output.output.get("tool_calls", []):
        if isinstance(call, dict):
            events.append(
                TraceEvent(
                    name=f"Tool: {call.get('name', 'unknown')}",
                    kind="tool",
                    timestamp=datetime.now(UTC),
                    duration_ms=call.get("duration_ms"),
                    details=call,
                )
            )

    return events


def is_provider_rate_limit_error_text(error: str | None) -> bool:
    if not error:
        return False
    lower = error.lower()
    return "rate limit" in lower or "ratelimiterror" in lower or "quota is exhausted" in lower


def is_provider_rate_limit_exception(exc: Exception) -> bool:
    return is_provider_rate_limit_error_text(f"{type(exc).__name__}: {exc}")


def clean_runner_error(exc: Exception, provider: str | None = None) -> str:
    if is_provider_rate_limit_exception(exc):
        return provider_rate_limit_message(provider)
    return f"{type(exc).__name__}: {exc}"


def _tool_metrics_from_output(output: RunnerOutput) -> list[ToolCallMetric]:
    metrics: list[ToolCallMetric] = []
    for call in output.output.get("tool_calls", []):
        if not isinstance(call, dict):
            continue
        raw_duration = call.get("duration_ms", 0.0)
        duration = raw_duration if isinstance(raw_duration, int | float) else 0.0
        details = {
            key: value
            for key, value in call.items()
            if key not in {"name", "duration_ms", "found"}
        }
        metrics.append(
            ToolCallMetric(
                name=str(call.get("name", "unknown")),
                duration_ms=round(float(duration), 1),
                found=call.get("found") if isinstance(call.get("found"), bool) else None,
                details=details,
            )
        )
    return metrics
