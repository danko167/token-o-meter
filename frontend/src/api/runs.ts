import { apiGet, apiPost } from './client';
import type {
  DecisionValue,
  HumanEvaluationRequest,
  RunBulkActionResult,
  RunListPage,
  RunRequest,
  RunResult,
  RunUsageSummary,
} from './types';

export const runsApi = {
  list: (includeArchived = false): Promise<RunResult[]> =>
    apiGet(includeArchived ? '/runs?include_archived=true' : '/runs'),
  listPage: (
    includeArchived = false,
    page = 1,
    pageSize = 25,
  ): Promise<RunListPage> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (includeArchived) {
      params.set('include_archived', 'true');
    }
    return apiGet(`/runs/page?${params.toString()}`);
  },
  get: (runId: string): Promise<RunResult> => apiGet(`/runs/${encodeURIComponent(runId)}`),
  latestByRunner: (
    scenarioId: string,
    includeArchived = false,
  ): Promise<RunResult[]> => {
    const params = new URLSearchParams({ scenario_id: scenarioId });
    if (includeArchived) {
      params.set('include_archived', 'true');
    }
    return apiGet(`/runs/latest-by-runner?${params.toString()}`);
  },
  usageSummary: (includeArchived = true): Promise<RunUsageSummary> =>
    apiGet(includeArchived ? '/runs/usage-summary?include_archived=true' : '/runs/usage-summary'),
  create: (request: RunRequest): Promise<RunResult> => apiPost('/runs', request),
  decide: (runId: string, decision: DecisionValue): Promise<RunResult> =>
    apiPost(`/runs/${encodeURIComponent(runId)}/decision`, { decision }),
  submitHumanEvaluation: (
    runId: string,
    evaluation: HumanEvaluationRequest,
  ): Promise<RunResult> =>
    apiPost(`/runs/${encodeURIComponent(runId)}/human-evaluation`, evaluation),
  bulkDelete: (runIds: string[]): Promise<RunBulkActionResult> =>
    apiPost('/runs/bulk-delete', { run_ids: runIds }),
  bulkArchive: (runIds: string[]): Promise<RunBulkActionResult> =>
    apiPost('/runs/bulk-archive', { run_ids: runIds }),
  bulkUnarchive: (runIds: string[]): Promise<RunBulkActionResult> =>
    apiPost('/runs/bulk-unarchive', { run_ids: runIds }),
};
