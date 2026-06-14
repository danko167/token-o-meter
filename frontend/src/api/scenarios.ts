import { apiDelete, apiGet, apiPost } from './client';
import type { Scenario, ScenarioCreate, ScenarioSummary } from './types';

export const scenariosApi = {
  list: (): Promise<ScenarioSummary[]> => apiGet('/scenarios'),
  get: (id: string): Promise<Scenario> => apiGet(`/scenarios/${encodeURIComponent(id)}`),
  create: (payload: ScenarioCreate): Promise<Scenario> => apiPost('/scenarios', payload),
  delete: (id: string): Promise<void> => apiDelete(`/scenarios/${encodeURIComponent(id)}`),
};
