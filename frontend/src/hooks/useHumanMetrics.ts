import { useQuery } from '@tanstack/react-query';
import { humanMetricsApi } from '../api/humanMetrics';
import { queryKeys } from '../api/queryKeys';
import type { ScenarioFamily } from '../api/types';

export function useHumanMetrics(scenarioId: string | null, family: ScenarioFamily | 'all') {
  return useQuery({
    queryKey: queryKeys.humanMetrics(scenarioId, family),
    queryFn: () => humanMetricsApi.get(scenarioId, family),
  });
}
