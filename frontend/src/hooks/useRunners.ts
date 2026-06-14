import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../api/queryKeys';
import { runnersApi } from '../api/runners';

export function useRunners() {
  return useQuery({
    queryKey: queryKeys.runners,
    queryFn: runnersApi.list,
  });
}
