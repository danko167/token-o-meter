import type { ScenarioFamily, ScenarioSummary } from '../api/types';

export const scenarioFamilyOptions: { value: ScenarioFamily | 'all'; label: string }[] = [
  { value: 'all', label: 'All families' },
  { value: 'customer_support', label: 'Customer support' },
  { value: 'policy_qa', label: 'Policy QA' },
  { value: 'git_diff_review', label: 'Git diff review' },
  { value: 'incident_triage', label: 'Incident triage' },
  { value: 'hiring_screening', label: 'Hiring screening' },
];

export function filterScenarios(
  scenarios: ScenarioSummary[],
  family: ScenarioFamily | 'all',
) {
  return family === 'all' ? scenarios : scenarios.filter((scenario) => scenario.family === family);
}
