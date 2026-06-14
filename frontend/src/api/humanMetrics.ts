import { apiGet } from './client';
import type { HumanMetricsResult, ScenarioFamily } from './types';

export const humanMetricsApi = {
  get: (
    scenarioId: string | null,
    family: ScenarioFamily | 'all',
  ): Promise<HumanMetricsResult> => {
    const params = new URLSearchParams();
    if (scenarioId) {
      params.set('scenario_id', scenarioId);
    } else if (family !== 'all') {
      params.set('family', family);
    }
    const query = params.toString() ? `?${params.toString()}` : '';
    return apiGet(`/human-metrics${query}`);
  },
};
