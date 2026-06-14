import { apiDelete, apiGet, apiPost } from './client';
import type { DemoDataResult, DemoExecutionStatus, ScenarioFamily } from './types';

export const demoDataApi = {
  add: (
    runsPerRunnerPerScenario: number,
    scenarioFamilies: ScenarioFamily[],
  ): Promise<DemoDataResult> =>
    apiPost('/demo-data', {
      runs_per_runner_per_scenario: runsPerRunnerPerScenario,
      scenario_families: scenarioFamilies,
    }),
  execute: (
    llmModel: string | null,
    runsPerRunnerPerScenario: number,
    scenarioFamilies: ScenarioFamily[],
  ): Promise<DemoDataResult> =>
    apiPost('/demo-data/execute', {
      llm_model: llmModel,
      runs_per_runner_per_scenario: runsPerRunnerPerScenario,
      scenario_families: scenarioFamilies,
    }),
  delete: (): Promise<DemoDataResult> => apiDelete('/demo-data'),
  executionStatus: (): Promise<DemoExecutionStatus> => apiGet('/demo-data/execute/status'),
};
