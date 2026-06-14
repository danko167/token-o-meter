/** Centralized React Query keys, so cache invalidation stays consistent. */
export const queryKeys = {
  scenarios: ['scenarios'] as const,
  scenario: (id: string) => ['scenarios', id] as const,
  runners: ['runners'] as const,
  runs: ['runs'] as const,
  runsList: (includeArchived: boolean) => ['runs', { includeArchived }] as const,
  runsPage: (includeArchived: boolean, page: number, pageSize: number) =>
    ['runs', 'page', { includeArchived, page, pageSize }] as const,
  latestRunsByRunner: (scenarioId: string | null, includeArchived: boolean) =>
    ['runs', 'latest-by-runner', { scenarioId, includeArchived }] as const,
  runUsageSummary: (includeArchived: boolean) =>
    ['runs', 'usage-summary', { includeArchived }] as const,
  run: (id: string) => ['runs', id] as const,
  recommendations: ['recommendations'] as const,
  recommendation: (scenarioId: string) => ['recommendations', scenarioId] as const,
  humanMetricsRoot: ['human-metrics'] as const,
  humanMetrics: (scenarioId: string | null, family: string) =>
    ['human-metrics', scenarioId ?? 'all', family] as const,
  dbHealth: ['health', 'db'] as const,
  pricing: ['pricing'] as const,
  demoExecutionStatus: ['demo-data', 'execute', 'status'] as const,
};
