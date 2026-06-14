import { apiGet } from './client';
import type { PricingResult } from './types';

export const pricingApi = {
  get: (): Promise<PricingResult> => apiGet('/pricing'),
};
