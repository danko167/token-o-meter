import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '../api/queryKeys';
import { scenariosApi } from '../api/scenarios';
import { notifyError, notifySuccess } from '../lib/notify';
import type { ScenarioCreate } from '../api/types';

export function useScenarios() {
  return useQuery({
    queryKey: queryKeys.scenarios,
    queryFn: scenariosApi.list,
  });
}

export function useScenario(scenarioId: string | null) {
  return useQuery({
    queryKey: queryKeys.scenario(scenarioId ?? ''),
    queryFn: () => scenariosApi.get(scenarioId as string),
    enabled: scenarioId !== null,
  });
}

export function useCreateScenario() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ScenarioCreate) => scenariosApi.create(payload),
    onSuccess: async (scenario) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.scenarios });
      queryClient.setQueryData(queryKeys.scenario(scenario.id), scenario);
      notifySuccess({
        title: 'Scenario added',
        message: `${scenario.name} is ready to run.`,
      });
    },
    onError: (error) => notifyError('Could not add scenario', error),
  });
}

export function useDeleteScenario() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scenariosApi.delete(id),
    onSuccess: async (_data, id) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.scenarios });
      queryClient.removeQueries({ queryKey: queryKeys.scenario(id) });
      notifySuccess({
        title: 'Scenario deleted',
        message: `${id} was removed.`,
      });
    },
    onError: (error) => notifyError('Could not delete scenario', error),
  });
}
