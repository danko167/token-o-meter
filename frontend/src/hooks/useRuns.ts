import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { queryKeys } from '../api/queryKeys';
import { runsApi } from '../api/runs';
import { logger } from '../lib/logger';
import { notifyError, notifySuccess } from '../lib/notify';
import type { ApiError } from '../api/client';
import type {
  DecisionValue,
  HumanEvaluationRequest,
  RunBulkActionResult,
  RunRequest,
  RunResult,
} from '../api/types';

export function useRuns(includeArchived = false) {
  return useQuery({
    queryKey: queryKeys.runsList(includeArchived),
    queryFn: () => runsApi.list(includeArchived),
  });
}

export function useRunsPage(includeArchived = false, page = 1, pageSize = 25) {
  return useQuery({
    queryKey: queryKeys.runsPage(includeArchived, page, pageSize),
    queryFn: () => runsApi.listPage(includeArchived, page, pageSize),
  });
}

export function invalidateRunDerivedQueries(queryClient: QueryClient) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.runs });
  void queryClient.invalidateQueries({ queryKey: queryKeys.recommendations });
  void queryClient.invalidateQueries({ queryKey: queryKeys.humanMetricsRoot });
}

export function useLatestRunsByRunner(scenarioId: string | null, includeArchived = false) {
  return useQuery({
    queryKey: queryKeys.latestRunsByRunner(scenarioId, includeArchived),
    queryFn: () => runsApi.latestByRunner(scenarioId as string, includeArchived),
    enabled: scenarioId !== null,
  });
}

export function useRunUsageSummary(includeArchived = true) {
  return useQuery({
    queryKey: queryKeys.runUsageSummary(includeArchived),
    queryFn: () => runsApi.usageSummary(includeArchived),
  });
}

export function useCreateRun() {
  const queryClient = useQueryClient();

  return useMutation<RunResult, ApiError, RunRequest>({
    mutationFn: runsApi.create,
    onSuccess: (result) => {
      logger.info('run completed', {
        runId: result.run_id,
        scenarioId: result.scenario_id,
        runner: result.runner,
        status: result.status,
        score: result.evaluation?.score,
      });
      invalidateRunDerivedQueries(queryClient);
    },
    onError: (error, variables) => {
      logger.error('run failed to execute', {
        scenarioId: variables.scenario_id,
        runner: variables.runner,
        error: error.message,
      });
    },
  });
}

export function useSubmitDecision() {
  const queryClient = useQueryClient();

  return useMutation<RunResult, ApiError, { runId: string; decision: DecisionValue }>({
    mutationFn: ({ runId, decision }) => runsApi.decide(runId, decision),
    onSuccess: (result) => {
      logger.info('run decision submitted', {
        runId: result.run_id,
        status: result.status,
        actions: result.actions,
      });
      notifySuccess({
        title: result.status === 'succeeded' ? 'Decision submitted' : 'Decision saved',
        message:
          result.status === 'succeeded'
            ? 'The run resumed and completed.'
            : `Run status is now ${result.status}.`,
      });
      invalidateRunDerivedQueries(queryClient);
    },
    onError: (error, variables) => {
      logger.error('run decision failed', {
        runId: variables.runId,
        decision: variables.decision,
        error: error.message,
      });
      notifyError('Decision failed', error);
    },
  });
}

export function useSubmitHumanEvaluation() {
  const queryClient = useQueryClient();

  return useMutation<RunResult, ApiError, { runId: string; evaluation: HumanEvaluationRequest }>({
    mutationFn: ({ runId, evaluation }) => runsApi.submitHumanEvaluation(runId, evaluation),
    onSuccess: (result) => {
      invalidateRunDerivedQueries(queryClient);
      logger.info('human evaluation submitted', { runId: result.run_id });
      notifySuccess({
        title: 'Human evaluation saved',
        message: `Saved evaluation for ${result.runner} on ${result.scenario_id}.`,
      });
    },
    onError: (error, variables) => {
      logger.error('human evaluation failed', {
        runId: variables.runId,
        error: error.message,
      });
      notifyError('Could not save human evaluation', error);
    },
  });
}

export function useBulkDeleteRuns() {
  const queryClient = useQueryClient();

  return useMutation<RunBulkActionResult, ApiError, string[]>({
    mutationFn: (runIds) => runsApi.bulkDelete(runIds),
    onSuccess: (result) => {
      logger.info('runs deleted', { count: result.count });
      notifySuccess({
        title: 'Runs deleted',
        message: `${result.count} run${result.count === 1 ? '' : 's'} deleted.`,
      });
      invalidateRunDerivedQueries(queryClient);
    },
    onError: (error) => notifyError('Could not delete runs', error),
  });
}

export function useBulkArchiveRuns() {
  const queryClient = useQueryClient();

  return useMutation<RunBulkActionResult, ApiError, string[]>({
    mutationFn: (runIds) => runsApi.bulkArchive(runIds),
    onSuccess: (result) => {
      logger.info('runs archived', { count: result.count });
      notifySuccess({
        title: 'Runs archived',
        message: `${result.count} run${result.count === 1 ? '' : 's'} archived.`,
      });
      invalidateRunDerivedQueries(queryClient);
    },
    onError: (error) => notifyError('Could not archive runs', error),
  });
}

export function useBulkUnarchiveRuns() {
  const queryClient = useQueryClient();

  return useMutation<RunBulkActionResult, ApiError, string[]>({
    mutationFn: (runIds) => runsApi.bulkUnarchive(runIds),
    onSuccess: (result) => {
      logger.info('runs unarchived', { count: result.count });
      notifySuccess({
        title: 'Runs restored',
        message: `${result.count} run${result.count === 1 ? '' : 's'} restored.`,
      });
      invalidateRunDerivedQueries(queryClient);
    },
    onError: (error) => notifyError('Could not restore runs', error),
  });
}
