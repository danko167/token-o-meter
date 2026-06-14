import { apiGet } from './client';
import type { DbHealth } from './types';

export const healthApi = {
  db: (): Promise<DbHealth> => apiGet('/health/db'),
};
