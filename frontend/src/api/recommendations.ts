import { apiGet } from './client';
import type { RecommendationResult } from './types';

export const recommendationsApi = {
  get: (scenarioId: string): Promise<RecommendationResult> =>
    apiGet(`/recommendations/${encodeURIComponent(scenarioId)}`),
};
