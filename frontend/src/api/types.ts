/**
 * Types mirroring the backend Pydantic schemas (app/schemas/*.py).
 * Keep these in sync with the backend — they are the contract.
 */

export type ScenarioFamily =
  | 'customer_support'
  | 'policy_qa'
  | 'git_diff_review'
  | 'incident_triage'
  | 'hiring_screening';

export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  family: ScenarioFamily;
  is_custom: boolean;
}

export interface Scenario extends ScenarioSummary {
  input: string;
  expected: Record<string, unknown>;
  required_fields: string[];
  forbidden_actions: string[];
  confidence_threshold: number | null;
}

export interface ScenarioCreate {
  id?: string;
  name: string;
  description: string;
  family: ScenarioFamily;
  input: string;
  expected: Record<string, unknown>;
  required_fields: string[];
  forbidden_actions: string[];
  confidence_threshold?: number | null;
}

export interface RunnerInfo {
  name: string;
  level: number;
  description: string;
}

export interface Metrics {
  duration_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
  retries: number;
  tool_calls: ToolCallMetric[];
}

export interface ToolCallMetric {
  name: string;
  duration_ms: number;
  found: boolean | null;
  details: Record<string, unknown>;
}

export interface EvaluationCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface Evaluation {
  score: number;
  checks: EvaluationCheck[];
}

export interface RunnerRecommendationStats {
  runner: string;
  level: number;
  total_runs: number;
  succeeded_runs: number;
  failed_runs: number;
  pending_runs: number;
  success_rate: number;
  average_score: number | null;
  average_duration_ms: number | null;
  average_cost_usd: number | null;
  average_retries: number | null;
  checkpoint_rate: number;
  reliable: boolean;
  reasons: string[];
}

export interface RecommendationResult {
  scenario_id: string;
  recommended_runner: string | null;
  recommended_level: number | null;
  strategy: string;
  primary_runner: string | null;
  fallback_runner: string | null;
  operational_complexity: number;
  simulation: StrategySimulation | null;
  confidence: number;
  summary: string;
  reasoning: string[];
  counterfactuals: CounterfactualExplanation[];
  runners: RunnerRecommendationStats[];
}

export interface CounterfactualExplanation {
  runner: string;
  outcome:
    | 'recommended'
    | 'primary'
    | 'fallback'
    | 'needs_data'
    | 'not_reliable'
    | 'higher_complexity'
    | 'superseded';
  summary: string;
  reasons: string[];
}

export interface StrategySimulation {
  sample_size: number;
  primary_success_rate: number;
  fallback_success_rate: number;
  projected_primary_handled_rate: number;
  projected_fallback_handled_rate: number;
  projected_human_intervention_rate: number;
  projected_success_rate: number;
  projected_average_cost_usd: number | null;
  projected_average_duration_ms: number | null;
}

export interface HumanMetricsResult {
  scenario_id: string | null;
  total_runs: number;
  checkpointed_runs: number;
  approved_runs: number;
  rejected_runs: number;
  pending_runs: number;
  escalated_runs: number;
  checkpoint_rate: number;
  approval_rate: number;
  rejection_rate: number;
  escalation_rate: number;
  intervention_rate_by_runner: Record<string, number>;
  totals_by_runner: Record<string, number>;
}

export type RunStatus = 'succeeded' | 'failed' | 'pending_approval';

export interface RunRequest {
  scenario_id: string;
  runner: string;
  llm_model?: string | null;
}

export interface PendingApproval {
  action: string;
  reason: string;
  details: Record<string, unknown>;
}

export interface HumanEvaluation {
  score: number;
  useful: boolean;
  correct: boolean;
  comment: string;
  created_at: string;
}

export interface HumanEvaluationRequest {
  score: number;
  useful: boolean;
  correct: boolean;
  comment: string;
}

export type TraceEventKind =
  | 'request'
  | 'runner'
  | 'tool'
  | 'evaluation'
  | 'checkpoint'
  | 'decision'
  | 'error';

export interface TraceEvent {
  name: string;
  kind: TraceEventKind;
  timestamp: string;
  duration_ms: number | null;
  prompt_tokens: number;
  completion_tokens: number;
  estimated_cost_usd: number;
  details: Record<string, unknown>;
}

export interface RunTrace {
  events: TraceEvent[];
}

export type DecisionValue = 'approve' | 'reject';

export interface RunDecisionRequest {
  decision: DecisionValue;
}

export interface RunResult {
  run_id: string;
  scenario_id: string;
  scenario_family: ScenarioFamily | null;
  runner: string;
  status: RunStatus;
  is_demo: boolean;
  archived: boolean;
  output: Record<string, unknown>;
  actions: string[];
  error: string | null;
  metrics: Metrics;
  evaluation: Evaluation | null;
  human_evaluation: HumanEvaluation | null;
  pending_approval: PendingApproval | null;
  trace: RunTrace;
  created_at: string;
}

export interface RunListPage {
  items: RunResult[];
  total: number;
  page: number;
  page_size: number;
}

export interface RunUsageTotals {
  runs: number;
  demo_runs: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
}

export interface RunModelUsage extends RunUsageTotals {
  model: string;
}

export interface RunRunnerModelUsage extends RunModelUsage {
  runner: string;
}

export interface RunRunnerUsage extends RunUsageTotals {
  runner: string;
  models: RunRunnerModelUsage[];
}

export interface RunUsageSummary {
  totals: RunUsageTotals;
  by_model: RunModelUsage[];
  by_runner: RunRunnerUsage[];
}

export interface DemoDataResult {
  created: number;
  deleted: number;
  skipped: number;
}

export interface DemoExecutionStatus {
  running: boolean;
  done: boolean;
  current: number;
  total: number;
  message: string;
  error: string | null;
}

export interface RunBulkActionResult {
  count: number;
}

export interface DbHealth {
  status: 'ok' | 'migration_pending';
  database_path: string;
  current_revision: string | null;
  head_revision: string | null;
}

export interface ModelPricing {
  provider: string;
  model: string;
  display_name: string;
  input_cost_per_million_tokens_usd: number | null;
  output_cost_per_million_tokens_usd: number | null;
  active: boolean;
  selectable: boolean;
  is_free: boolean;
  notes: string;
}

export interface PricingResult {
  currency: string;
  unit: string;
  models: ModelPricing[];
}
