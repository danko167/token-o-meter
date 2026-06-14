import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { demoDataApi } from '../api/demoData';
import { queryKeys } from '../api/queryKeys';
import { invalidateRunDerivedQueries } from './useRuns';
import type { ScenarioFamily } from '../api/types';

export function useAddDemoData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      runsPerRunnerPerScenario,
      scenarioFamilies,
    }: {
      runsPerRunnerPerScenario: number;
      scenarioFamilies: ScenarioFamily[];
    }) => demoDataApi.add(runsPerRunnerPerScenario, scenarioFamilies),
    onSuccess: () => invalidateRunDerivedQueries(queryClient),
  });
}

export function useExecuteDemoData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      llmModel,
      runsPerRunnerPerScenario,
      scenarioFamilies,
    }: {
      llmModel: string | null;
      runsPerRunnerPerScenario: number;
      scenarioFamilies: ScenarioFamily[];
    }) => demoDataApi.execute(llmModel, runsPerRunnerPerScenario, scenarioFamilies),
    onSuccess: () => invalidateRunDerivedQueries(queryClient),
  });
}

export function useDemoExecutionStatus(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.demoExecutionStatus,
    queryFn: demoDataApi.executionStatus,
    enabled,
    refetchInterval: enabled ? 1000 : false,
  });
}

export function useDeleteDemoData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: demoDataApi.delete,
    onSuccess: () => invalidateRunDerivedQueries(queryClient),
  });
}
