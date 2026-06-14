import { useQuery } from '@tanstack/react-query';
import { healthApi } from '../api/health';
import { queryKeys } from '../api/queryKeys';

export function useDbHealth() {
  return useQuery({
    queryKey: queryKeys.dbHealth,
    queryFn: healthApi.db,
  });
}
