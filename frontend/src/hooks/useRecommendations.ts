import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../api/queryKeys';
import { recommendationsApi } from '../api/recommendations';

export function useRecommendation(scenarioId: string | null) {
  return useQuery({
    queryKey: queryKeys.recommendation(scenarioId ?? ''),
    queryFn: () => recommendationsApi.get(scenarioId as string),
    enabled: scenarioId !== null,
  });
}
