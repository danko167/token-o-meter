import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../api/queryKeys';
import { pricingApi } from '../api/pricing';

export function usePricing() {
  return useQuery({
    queryKey: queryKeys.pricing,
    queryFn: pricingApi.get,
  });
}
