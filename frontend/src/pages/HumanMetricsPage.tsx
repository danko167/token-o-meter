import { useState } from 'react';
import { Alert, Card, Grid, Group, Progress, Select, Stack, Table, Text, Title } from '@mantine/core';
import { IconFlask, IconUserCheck } from '@tabler/icons-react';
import { useHumanMetrics } from '../hooks/useHumanMetrics';
import { useScenarios } from '../hooks/useScenarios';
import { HelpIcon } from '../components/HelpIcon';
import { filterScenarios, scenarioFamilyOptions } from '../lib/scenarioFamilies';
import type { ScenarioFamily } from '../api/types';

export function HumanMetricsPage() {
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [family, setFamily] = useState<ScenarioFamily | 'all'>('all');
  const scenarios = useScenarios();
  const metrics = useHumanMetrics(scenarioId, family);
  const data = metrics.data;
  const scenarioOptions = [
    { value: '__all__', label: 'All scenarios' },
    ...filterScenarios(scenarios.data ?? [], family).map((scenario) => ({
      value: scenario.id,
      label: scenario.name,
    })),
  ];

  const handleScenarioChange = (value: string | null) => {
    setScenarioId(value === '__all__' ? null : value);
  };

  return (
    <Stack>
      <Alert color="blue" variant="light">
        Human metrics show where autonomy stopped: checkpoints, approvals, rejections,
        escalations, and intervention rate by runner.
      </Alert>
      <Select
        label={
          <Group gap={4}>
            Scenario family
            <HelpIcon label="Filter human-impact metrics to one task type, or leave it on all families." />
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
            <HelpIcon label="Choose one scenario or all scenarios to see where human review was needed." />
          </Group>
        }
        data={scenarioOptions}
        value={scenarioId ?? '__all__'}
        onChange={handleScenarioChange}
        leftSection={<IconFlask size={16} />}
        disabled={scenarios.isLoading}
        searchable
      />

      {data && (
        <>
          {data.total_runs === 0 && (
            <Card withBorder padding="md" radius="md">
              <Text c="dimmed" ta="center">
                No runs yet. Add demo data or run a human-checkpoint scenario to populate
                this dashboard.
              </Text>
            </Card>
          )}
          <Grid>
            <MetricCard help="All recorded runs included in this filter." label="Total runs" value={String(data.total_runs)} />
            <MetricCard help="Runs that paused for human review before completion." label="Checkpoints" value={String(data.checkpointed_runs)} />
            <MetricCard help="Checkpointed runs where the proposed action was approved." label="Approved" value={String(data.approved_runs)} />
            <MetricCard help="Checkpointed runs where the proposed action was rejected or redirected." label="Rejected" value={String(data.rejected_runs)} />
          </Grid>

          <Card withBorder padding="md" radius="md">
            <Stack gap="sm">
              <Group gap={4}>
                <Title order={5}>Human Impact Rates</Title>
                <HelpIcon label="These rates show how often automation needed human oversight, and whether humans agreed with proposed actions." />
              </Group>
              <RateBar help="Share of runs that paused for human approval." label="Checkpoint rate" value={data.checkpoint_rate} />
              <RateBar help="Share of checkpointed runs that humans approved." label="Approval rate" value={data.approval_rate} />
              <RateBar help="Share of checkpointed runs that humans rejected." label="Rejection rate" value={data.rejection_rate} />
              <RateBar help="Share of runs that ended in an escalation action." label="Escalation rate" value={data.escalation_rate} />
            </Stack>
          </Card>

          <Card withBorder padding="md" radius="md">
            <Stack gap="sm">
              <Group gap={4}>
                <Title order={5}>Intervention By Runner</Title>
                <HelpIcon label="Compares which abstraction levels required human involvement most often." />
              </Group>
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Runner</Table.Th>
                    <Table.Th>Runs</Table.Th>
                    <Table.Th>Intervention rate</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {Object.entries(data.totals_by_runner).map(([runner, total]) => (
                    <Table.Tr key={runner}>
                      <Table.Td>{runner}</Table.Td>
                      <Table.Td>{total}</Table.Td>
                      <Table.Td>{formatPercent(data.intervention_rate_by_runner[runner] ?? 0)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Stack>
          </Card>
        </>
      )}
    </Stack>
  );
}

export default HumanMetricsPage;

function MetricCard({ help, label, value }: { help: string; label: string; value: string }) {
  return (
    <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
      <Card withBorder padding="md" radius="md">
        <Stack gap={4}>
          <IconUserCheck size={20} />
          <Text size="xl" fw={700}>
            {value}
          </Text>
          <Group gap={4}>
            <Text size="sm" c="dimmed">{label}</Text>
            <HelpIcon label={help} />
          </Group>
        </Stack>
      </Card>
    </Grid.Col>
  );
}

function RateBar({ help, label, value }: { help: string; label: string; value: number }) {
  return (
    <Stack gap={4}>
      <Group gap={4}>
        <Text size="sm">{label}: {formatPercent(value)}</Text>
        <HelpIcon label={help} />
      </Group>
      <Progress value={value * 100} />
    </Stack>
  );
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}
