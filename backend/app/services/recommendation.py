"""Recommendation engine for choosing the cheapest reliable abstraction."""

from __future__ import annotations

from collections import defaultdict

from app.runners.base import RunnerRegistry
from app.schemas.recommendation import (
    CounterfactualExplanation,
    RecommendationResult,
    RunnerRecommendationStats,
    StrategySimulation,
)
from app.schemas.run import RunResult
from app.services.execution import RunStore
from app.services.human_metrics import was_checkpointed

MIN_AVERAGE_SCORE = 80.0
MIN_SUCCESS_RATE = 0.8


class RecommendationService:
    def __init__(self, registry: RunnerRegistry, store: RunStore) -> None:
        self._registry = registry
        self._store = store

    def recommend(self, scenario_id: str) -> RecommendationResult:
        runs = self._store.list(scenario_id=scenario_id)
        runner_info = {runner.name: runner for runner in self._registry.list()}
        by_runner: dict[str, list[RunResult]] = defaultdict(list)
        for run in runs:
            by_runner[run.runner].append(run)

        stats = [
            _stats_for_runner(name, runner.level, by_runner.get(name, []))
            for name, runner in sorted(runner_info.items(), key=lambda item: item[1].level)
        ]

        candidates = [item for item in stats if item.reliable]
        if not candidates:
            return RecommendationResult(
                scenario_id=scenario_id,
                recommended_runner=None,
                recommended_level=None,
                strategy="needs_more_data",
                operational_complexity=1,
                simulation=None,
                confidence=0.0,
                summary="No runner has enough reliable successful data for this scenario yet.",
                reasoning=[
                    "Run the scenario against multiple runners first.",
                    f"A runner is considered reliable at {MIN_SUCCESS_RATE:.0%} success rate "
                    f"and average score >= {MIN_AVERAGE_SCORE:.0f}.",
                ],
                counterfactuals=_counterfactuals(stats, None, None),
                runners=stats,
            )

        recommended = min(
            candidates,
            key=lambda item: (
                item.level,
                item.average_cost_usd if item.average_cost_usd is not None else float("inf"),
                item.average_duration_ms
                if item.average_duration_ms is not None
                else float("inf"),
            ),
        )
        confidence = _confidence(recommended)
        fallback = _fallback_strategy(stats, recommended)
        strategy = "single_runner"
        primary_runner = recommended.runner
        fallback_runner = None
        operational_complexity = _complexity(recommended.level)
        summary = (
            f"Recommended abstraction: L{recommended.level} {recommended.runner}. "
            "It is the lowest-level runner that meets the reliability threshold."
        )
        reasoning = [
            f"{recommended.runner} has a {recommended.success_rate:.0%} success rate.",
            f"Average score is {recommended.average_score:.1f}.",
            f"Average latency is {recommended.average_duration_ms:.1f} ms.",
            f"Average estimated cost is ${recommended.average_cost_usd:.6f}.",
            f"Operational complexity score: {operational_complexity}/5.",
        ]
        if fallback is not None:
            strategy = "rules_plus_fallback"
            primary_runner = fallback.runner
            fallback_runner = recommended.runner
            operational_complexity = (
                max(_complexity(fallback.level), _complexity(recommended.level)) + 1
            )
            operational_complexity = min(operational_complexity, 5)
            summary = (
                f"Recommended strategy: L{fallback.level} {fallback.runner} first, "
                f"fall back to L{recommended.level} {recommended.runner} when checks fail."
            )
            reasoning = [
                f"{fallback.runner} is cheaper/lower-level and has enough successful runs "
                "to handle a first pass.",
                f"{recommended.runner} is the reliable fallback with "
                f"{recommended.success_rate:.0%} success and score "
                f"{recommended.average_score:.1f}.",
                "This blended strategy preserves cheap paths while keeping a reliable "
                "escape hatch.",
                f"Operational complexity score: {operational_complexity}/5.",
            ]
        return RecommendationResult(
            scenario_id=scenario_id,
            recommended_runner=recommended.runner,
            recommended_level=recommended.level,
            strategy=strategy,
            primary_runner=primary_runner,
            fallback_runner=fallback_runner,
            operational_complexity=operational_complexity,
            simulation=_simulate_strategy(recommended, fallback),
            confidence=confidence,
            summary=summary,
            reasoning=reasoning,
            counterfactuals=_counterfactuals(stats, recommended, fallback),
            runners=stats,
        )


def _stats_for_runner(
    runner: str, level: int, runs: list[RunResult]
) -> RunnerRecommendationStats:
    total = len(runs)
    succeeded = sum(1 for run in runs if run.status == "succeeded")
    failed = sum(1 for run in runs if run.status == "failed")
    pending = sum(1 for run in runs if run.status == "pending_approval")
    checkpointed = sum(1 for run in runs if was_checkpointed(run))
    scored = [
        run.evaluation.score
        for run in runs
        if run.status == "succeeded" and run.evaluation is not None
    ]
    successful = [run for run in runs if run.status == "succeeded"]

    average_score = _average(scored)
    average_duration = _average([run.metrics.duration_ms for run in successful])
    average_cost = _average([run.metrics.estimated_cost_usd for run in successful])
    average_retries = _average([run.metrics.retries for run in successful])
    success_rate = succeeded / total if total else 0.0
    checkpoint_rate = checkpointed / total if total else 0.0

    reasons: list[str] = []
    if total == 0:
        reasons.append("No runs recorded.")
    if total > 0 and success_rate < MIN_SUCCESS_RATE:
        reasons.append(f"Success rate {success_rate:.0%} is below {MIN_SUCCESS_RATE:.0%}.")
    if average_score is None:
        reasons.append("No successful evaluated runs.")
    elif average_score < MIN_AVERAGE_SCORE:
        reasons.append(f"Average score {average_score:.1f} is below {MIN_AVERAGE_SCORE:.0f}.")

    reliable = total > 0 and success_rate >= MIN_SUCCESS_RATE and (
        average_score is not None and average_score >= MIN_AVERAGE_SCORE
    )
    if reliable:
        reasons.append("Meets reliability threshold.")

    return RunnerRecommendationStats(
        runner=runner,
        level=level,
        total_runs=total,
        succeeded_runs=succeeded,
        failed_runs=failed,
        pending_runs=pending,
        success_rate=round(success_rate, 3),
        average_score=round(average_score, 1) if average_score is not None else None,
        average_duration_ms=round(average_duration, 1) if average_duration is not None else None,
        average_cost_usd=round(average_cost, 8) if average_cost is not None else None,
        average_retries=round(average_retries, 2) if average_retries is not None else None,
        checkpoint_rate=round(checkpoint_rate, 3),
        reliable=reliable,
        reasons=reasons,
    )


def _average(values: list[float | int]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _confidence(stats: RunnerRecommendationStats) -> float:
    if stats.average_score is None:
        return 0.0
    score_factor = min(stats.average_score / 100, 1.0)
    return round(stats.success_rate * score_factor, 3)


def _fallback_strategy(
    stats: list[RunnerRecommendationStats],
    recommended: RunnerRecommendationStats,
) -> RunnerRecommendationStats | None:
    cheaper = [
        item
        for item in stats
        if item.level < recommended.level
        and item.total_runs > 0
        and item.success_rate >= 0.7
        and item.average_score is not None
        and item.average_score >= 60
    ]
    if not cheaper:
        return None
    return min(cheaper, key=lambda item: item.level)


def _complexity(level: int) -> int:
    return min(max(level, 1), 5)


def _simulate_strategy(
    recommended: RunnerRecommendationStats,
    primary: RunnerRecommendationStats | None,
) -> StrategySimulation:
    if primary is None:
        human_rate = recommended.checkpoint_rate
        return StrategySimulation(
            sample_size=recommended.total_runs,
            primary_success_rate=recommended.success_rate,
            fallback_success_rate=0.0,
            projected_primary_handled_rate=recommended.success_rate,
            projected_fallback_handled_rate=0.0,
            projected_human_intervention_rate=human_rate,
            projected_success_rate=recommended.success_rate,
            projected_average_cost_usd=recommended.average_cost_usd,
            projected_average_duration_ms=recommended.average_duration_ms,
        )

    primary_success = primary.success_rate
    fallback_attempt_rate = max(0.0, 1.0 - primary_success)
    fallback_handled = fallback_attempt_rate * recommended.success_rate
    human_rate = fallback_attempt_rate * recommended.checkpoint_rate
    projected_success = min(1.0, primary_success + fallback_handled)
    projected_cost = _projected_weighted(
        primary.average_cost_usd, recommended.average_cost_usd, fallback_attempt_rate
    )
    projected_duration = _projected_weighted(
        primary.average_duration_ms, recommended.average_duration_ms, fallback_attempt_rate
    )

    return StrategySimulation(
        sample_size=primary.total_runs + recommended.total_runs,
        primary_success_rate=primary_success,
        fallback_success_rate=recommended.success_rate,
        projected_primary_handled_rate=round(primary_success, 3),
        projected_fallback_handled_rate=round(fallback_handled, 3),
        projected_human_intervention_rate=round(human_rate, 3),
        projected_success_rate=round(projected_success, 3),
        projected_average_cost_usd=projected_cost,
        projected_average_duration_ms=projected_duration,
    )


def _projected_weighted(
    primary_value: float | None, fallback_value: float | None, fallback_attempt_rate: float
) -> float | None:
    if primary_value is None and fallback_value is None:
        return None
    primary = primary_value or 0.0
    fallback = fallback_value or 0.0
    return round(primary + fallback_attempt_rate * fallback, 8)


def _counterfactuals(
    stats: list[RunnerRecommendationStats],
    recommended: RunnerRecommendationStats | None,
    fallback_primary: RunnerRecommendationStats | None,
) -> list[CounterfactualExplanation]:
    explanations: list[CounterfactualExplanation] = []
    for item in stats:
        if item.total_runs == 0:
            explanations.append(
                CounterfactualExplanation(
                    runner=item.runner,
                    outcome="needs_data",
                    summary=f"Not enough evidence for {item.runner} yet.",
                    reasons=item.reasons,
                )
            )
            continue

        if fallback_primary is not None and item.runner == fallback_primary.runner:
            explanations.append(
                CounterfactualExplanation(
                    runner=item.runner,
                    outcome="primary",
                    summary=(
                        f"{item.runner} is useful as the cheap first pass, but it does "
                        "not meet the full reliability threshold alone."
                    ),
                    reasons=item.reasons,
                )
            )
            continue

        if recommended is not None and item.runner == recommended.runner:
            outcome = "fallback" if fallback_primary is not None else "recommended"
            explanations.append(
                CounterfactualExplanation(
                    runner=item.runner,
                    outcome=outcome,
                    summary=(
                        f"{item.runner} is the reliable "
                        f"{'fallback' if outcome == 'fallback' else 'recommendation'}."
                    ),
                    reasons=item.reasons,
                )
            )
            continue

        if not item.reliable:
            explanations.append(
                CounterfactualExplanation(
                    runner=item.runner,
                    outcome="not_reliable",
                    summary=f"{item.runner} is not recommended as the main path yet.",
                    reasons=item.reasons,
                )
            )
            continue

        if recommended is not None and item.level > recommended.level:
            explanations.append(
                CounterfactualExplanation(
                    runner=item.runner,
                    outcome="higher_complexity",
                    summary=(
                        f"{item.runner} is reliable, but a lower-level runner already "
                        "meets the target."
                    ),
                    reasons=[
                        f"Level {item.level} adds more operational complexity than "
                        f"Level {recommended.level}.",
                        "Use it when the scenario needs extra judgment, tools, or human review.",
                    ],
                )
            )
            continue

        explanations.append(
            CounterfactualExplanation(
                runner=item.runner,
                outcome="superseded",
                summary=f"{item.runner} was beaten by stronger historical evidence.",
                reasons=item.reasons,
            )
        )
    return explanations
