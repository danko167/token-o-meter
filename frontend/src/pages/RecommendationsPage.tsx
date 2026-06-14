import { useState } from 'react';
import { Alert, Badge, Card, Code, Group, Loader, ScrollArea, Select, Stack, Table, Text, Title } from '@mantine/core';
import { IconBulb, IconFlask } from '@tabler/icons-react';
import { useRecommendation } from '../hooks/useRecommendations';
import { useScenarios } from '../hooks/useScenarios';
import { HelpIcon } from '../components/HelpIcon';
import { filterScenarios, scenarioFamilyOptions } from '../lib/scenarioFamilies';
import type { ScenarioFamily } from '../api/types';

export function RecommendationsPage() {
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [family, setFamily] = useState<ScenarioFamily | 'all'>('all');
  const scenarios = useScenarios();
  const recommendation = useRecommendation(scenarioId);
  const scenarioOptions = filterScenarios(scenarios.data ?? [], family).map((scenario) => ({
    value: scenario.id,
    label: scenario.name,
  }));

  return (
    <Stack>
      <Alert color="blue" variant="light">
        Recommendations use recorded evidence. Add demo data or run comparisons first if
        this page is empty.
      </Alert>
      <Select
        label={
          <Group gap={4}>
            Scenario family
            <HelpIcon label="Filter recommendations to one task type. Each family has different expectations and scoring rules." />
          </Group>
        }
        data={scenarioFamilyOptions}
        value={family}
        onChange={(value) => {
          setFamily((value ?? 'all') as ScenarioFamily | 'all');
          setScenarioId(null);
        }}
      />
      <Select
        label={
          <Group gap={4}>
            Scenario
            <HelpIcon label="Recommendations are scenario-specific because a cheap approach may work for one case and fail another." />
          </Group>
        }
        placeholder="Choose a scenario"
        data={scenarioOptions}
        value={scenarioId}
        onChange={setScenarioId}
        leftSection={<IconFlask size={16} />}
        searchable
        disabled={scenarios.isLoading}
      />

      {!scenarioId && (
        <Text c="dimmed" ta="center" py="xl">
          Choose a scenario to see the recommended abstraction from recorded runs.
          Use Add demo data if you want an immediate walkthrough.
        </Text>
      )}

      {scenarioId && recommendation.isLoading && <Loader size="sm" />}

      {recommendation.data && (
        <Stack>
          <Alert
            color={recommendation.data.recommended_runner ? 'green' : 'yellow'}
            icon={<IconBulb size={18} />}
            title={
              <Group gap={4} wrap="nowrap">
                Recommendation
                <HelpIcon label="'single_runner' means one abstraction level is reliable enough on its own. 'rules_plus_fallback' means a cheaper primary runner handles most cases, with a more reliable fallback runner stepping in when its checks fail." />
              </Group>
            }
          >
            <Stack gap="xs">
              <Text size="sm">{recommendation.data.summary}</Text>
              {recommendation.data.recommended_runner && (
                <>
                  <Badge color="green" variant="light">
                    {recommendation.data.strategy}
                  </Badge>
                  <Badge color="blue" variant="light">
                    Primary: {recommendation.data.primary_runner}
                  </Badge>
                  {recommendation.data.fallback_runner && (
                    <Badge color="violet" variant="light">
                      Fallback: {recommendation.data.fallback_runner}
                    </Badge>
                  )}
                  <Badge color="gray" variant="light">
                    Complexity {recommendation.data.operational_complexity}/5
                  </Badge>
                </>
              )}
              {recommendation.data.reasoning.length > 0 && (
                <Code block>{recommendation.data.reasoning.join('\n')}</Code>
              )}
            </Stack>
          </Alert>
          {recommendation.data.recommended_runner === null && (
            <Card withBorder padding="md" radius="md">
              <Text c="dimmed" ta="center">
                There is not enough evidence yet. Run this scenario against multiple runners
                from Compare, or add demo data from the header.
              </Text>
            </Card>
          )}

          {recommendation.data.simulation && (
            <Card withBorder padding="md" radius="md">
              <Stack gap="sm">
                <Group gap={4}>
                  <Title order={5}>Strategy Simulation</Title>
                  <HelpIcon label="A projection from historical runs: how often the primary runner handles the case, when fallback is needed, and how often a human may intervene." />
                </Group>
                <ScrollArea type="auto" offsetScrollbars>
                  <Table striped miw={480}>
                    <Table.Tbody>
                      <Table.Tr>
                        <Table.Td>Historical sample</Table.Td>
                        <Table.Td>{recommendation.data.simulation.sample_size} runs</Table.Td>
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td>Primary handled</Table.Td>
                        <Table.Td>{formatPercent(recommendation.data.simulation.projected_primary_handled_rate)}</Table.Td>
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td>Fallback handled</Table.Td>
                        <Table.Td>{formatPercent(recommendation.data.simulation.projected_fallback_handled_rate)}</Table.Td>
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td>Human intervention</Table.Td>
                        <Table.Td>{formatPercent(recommendation.data.simulation.projected_human_intervention_rate)}</Table.Td>
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td>Projected success</Table.Td>
                        <Table.Td>{formatPercent(recommendation.data.simulation.projected_success_rate)}</Table.Td>
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td>Projected latency</Table.Td>
                        <Table.Td>
                          {formatNumber(recommendation.data.simulation.projected_average_duration_ms)} ms
                        </Table.Td>
                      </Table.Tr>
                      <Table.Tr>
                        <Table.Td>Projected cost</Table.Td>
                        <Table.Td>
                          {formatCost(recommendation.data.simulation.projected_average_cost_usd)}
                        </Table.Td>
                      </Table.Tr>
                    </Table.Tbody>
                  </Table>
                </ScrollArea>
              </Stack>
            </Card>
          )}

          {recommendation.data.counterfactuals.length > 0 && (
            <Card withBorder padding="md" radius="md">
              <Stack gap="sm">
                <Group gap={4}>
                  <Title order={5}>Why Not Other Runners?</Title>
                  <HelpIcon label="For every runner with recorded data, this explains its role in the recommendation: chosen as primary or fallback, or why it was not picked as the main strategy." />
                </Group>
                <ScrollArea type="auto" offsetScrollbars>
                  <Table striped highlightOnHover miw={640}>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Runner</Table.Th>
                        <Table.Th>Outcome</Table.Th>
                        <Table.Th>Explanation</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {recommendation.data.counterfactuals.map((item) => (
                        <Table.Tr key={item.runner}>
                          <Table.Td>{item.runner}</Table.Td>
                          <Table.Td>
                            <Badge color={counterfactualColor(item.outcome)} variant="light">
                              {formatOutcome(item.outcome)}
                            </Badge>
                          </Table.Td>
                          <Table.Td>
                            <Stack gap={2}>
                              <Text size="sm">{item.summary}</Text>
                              {item.reasons.map((reason) => (
                                <Text key={reason} size="xs" c="dimmed">
                                  {reason}
                                </Text>
                              ))}
                            </Stack>
                          </Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </ScrollArea>
              </Stack>
            </Card>
          )}

          <Card withBorder padding="md" radius="md">
            <Stack gap="sm">
              <Group gap={4}>
                <Title order={5}>Runner Evidence</Title>
                <HelpIcon label="Historical results used by the recommendation engine: run count, success rate, score, latency, and cost. Status is 'Reliable' once a runner reaches at least 80% success rate and an average score of 80 or higher." />
              </Group>
              <ScrollArea type="auto" offsetScrollbars>
              <Table striped highlightOnHover miw={720}>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Runner</Table.Th>
                    <Table.Th>Runs</Table.Th>
                    <Table.Th>Success</Table.Th>
                    <Table.Th>Score</Table.Th>
                    <Table.Th>Latency</Table.Th>
                    <Table.Th>Cost</Table.Th>
                    <Table.Th>Status</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {recommendation.data.runners.map((runner) => (
                    <Table.Tr key={runner.runner}>
                      <Table.Td>
                        L{runner.level} {runner.runner}
                      </Table.Td>
                      <Table.Td>{runner.total_runs}</Table.Td>
                      <Table.Td>{Math.round(runner.success_rate * 100)}%</Table.Td>
                      <Table.Td>{formatNumber(runner.average_score)}</Table.Td>
                      <Table.Td>{formatNumber(runner.average_duration_ms)} ms</Table.Td>
                      <Table.Td>{formatCost(runner.average_cost_usd)}</Table.Td>
                      <Table.Td>
                        <Badge color={runner.reliable ? 'green' : 'gray'} variant="light">
                          {runner.reliable ? 'Reliable' : 'Needs data'}
                        </Badge>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
              </ScrollArea>
            </Stack>
          </Card>
        </Stack>
      )}
    </Stack>
  );
}

export default RecommendationsPage;

function formatNumber(value: number | null) {
  return value === null ? '-' : value.toFixed(1);
}

function formatCost(value: number | null) {
  return value === null ? '-' : `$${value.toFixed(6)}`;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatOutcome(value: string) {
  return value.replaceAll('_', ' ');
}

function counterfactualColor(value: string) {
  switch (value) {
    case 'recommended':
    case 'primary':
    case 'fallback':
      return 'green';
    case 'higher_complexity':
    case 'superseded':
      return 'blue';
    case 'not_reliable':
      return 'yellow';
    default:
      return 'gray';
  }
}
