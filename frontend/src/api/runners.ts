import { apiGet } from './client';
import type { RunnerInfo } from './types';

export const runnersApi = {
  list: (): Promise<RunnerInfo[]> => apiGet('/runners'),
};
