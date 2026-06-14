import { useMemo, useRef, useState } from 'react';
import { Alert, Badge, Button, Card, Grid, Group, Modal, ScrollArea, Select, Stack, Text } from '@mantine/core';
import { IconFlask, IconPlayerPlay } from '@tabler/icons-react';
import { useScenario, useScenarios } from '../hooks/useScenarios';
import { useRunners } from '../hooks/useRunners';
import { useCreateRun, useLatestRunsByRunner } from '../hooks/useRuns';
import { ScenarioDetailCard } from '../components/ScenarioDetailCard';
import { ComparisonTable } from '../components/ComparisonTable';
import { HelpIcon } from '../components/HelpIcon';
import { RunResultPanel } from '../components/RunResultPanel';
import { OpenRouterModelSelect } from '../components/OpenRouterModelSelect';
import { useRecommendation } from '../hooks/useRecommendations';
import { filterScenarios, scenarioFamilyOptions } from '../lib/scenarioFamilies';
import { notifySuccess, notifyWarning } from '../lib/notify';
import type { RunResult, ScenarioFamily } from '../api/types';

export function ComparePage() {
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [freshResults, setFreshResults] = useState<Record<string, RunResult>>({});
  const [runnerErrors, setRunnerErrors] = useState<Record<string, string>>({});
  const [runningRunner, setRunningRunner] = useState<string | null>(null);
  const [selected, setSelected] = useState<RunResult | null>(null);
  const [family, setFamily] = useState<ScenarioFamily | 'all'>('all');
  const [llmModel, setLlmModel] = useState<string | null>(null);
  const scenarioIdRef = useRef(scenarioId);

  const scenarios = useScenarios();
  const scenario = useScenario(scenarioId);
  const runners = useRunners();
  const latestRuns = useLatestRunsByRunner(scenarioId);
  const createRun = useCreateRun();
  const recommendation = useRecommendation(scenarioId);

  const scenarioOptions = filterScenarios(scenarios.data ?? [], family).map((s) => ({
    value: s.id,
    label: s.name,
  }));

  const latestByRunner = useMemo(() => {
    const map: Record<string, RunResult> = {};
    if (!scenarioId) return map;
    for (const run of latestRuns.data ?? []) {
      map[run.runner] = run;
    }
    return map;
  }, [latestRuns.data, scenarioId]);

  const results = useMemo(() => {
    const merged: Record<string, RunResult> = { ...latestByRunner, ...freshResults };
    for (const runner of Object.keys(runnerErrors)) {
      delete merged[runner];
    }
    return merged;
  }, [latestByRunner, freshResults, runnerErrors]);
  const isRunningAll = runningRunner !== null;

  const handleScenarioChange = (value: string | null) => {
    scenarioIdRef.current = value;
    setScenarioId(value);
    setFreshResults({});
    setRunnerErrors({});
    setSelected(null);
  };

  const runAll = async () => {
    if (!scenarioId) return;
    const runScenarioId = scenarioId;
    setFreshResults({});
    setRunnerErrors({});
    let succeeded = 0;
    let failed = 0;
    let pendingApproval = 0;
    let requestErrors = 0;
    for (const r of runners.data ?? []) {
      setRunningRunner(r.name);
      try {
        const result = await createRun.mutateAsync({
          scenario_id: runScenarioId,
          runner: r.name,
          llm_model: r.level >= 2 ? llmModel : null,
        });
        if (scenarioIdRef.current === runScenarioId) {
          setFreshResults((prev) => ({ ...prev, [r.name]: result }));
        }
        if (result.status === 'succeeded') {
          succeeded += 1;
        } else if (result.status === 'pending_approval') {
          pendingApproval += 1;
        } else {
          failed += 1;
        }
      } catch (err) {
        requestErrors += 1;
        if (scenarioIdRef.current === runScenarioId) {
          setRunnerErrors((prev) => ({
            ...prev,
            [r.name]: err instanceof Error ? err.message : 'Run failed.',
          }));
        }
      }
    }
    setRunningRunner(null);
    void recommendation.refetch();
    if (requestErrors > 0 || failed > 0) {
      notifyWarning({
        title: 'Comparison finished with issues',
        message: `${succeeded} succeeded, ${pendingApproval} pending approval, ${failed + requestErrors} failed.`,
      });
    } else {
      notifySuccess({
        title: 'Comparison complete',
        message: `${succeeded} succeeded${pendingApproval ? `, ${pendingApproval} pending approval` : ''}.`,
      });
    }
  };

  const handleResultUpdate = (updated: RunResult) => {
    setFreshResults((prev) => ({ ...prev, [updated.runner]: updated }));
    setSelected(updated);
  };

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 4 }}>
        <Stack>
          <Alert color="blue" variant="light">
            Run all abstraction levels for one scenario, compare their evidence, then use
            the recommendation below to choose a practical strategy.
          </Alert>
          <Select
            label={
              <Group gap={4}>
                Scenario family
                <HelpIcon label="Filter to one task type before comparing runners. Different families have different output shapes and scoring rules." />
              </Group>
            }
            data={scenarioFamilyOptions}
            value={family}
            disabled={isRunningAll}
            onChange={(value) => {
              setFamily((value ?? 'all') as ScenarioFamily | 'all');
              handleScenarioChange(null);
            }}
          />
          <Select
            label={
              <Group gap={4}>
                Scenario
                <HelpIcon label="Run all abstraction levels against this same benchmark case so their accuracy, cost, and latency are comparable." />
              </Group>
            }
            placeholder="Choose a scenario"
            data={scenarioOptions}
            value={scenarioId}
            onChange={handleScenarioChange}
            leftSection={<IconFlask size={16} />}
            searchable
            disabled={scenarios.isLoading || isRunningAll}
          />
          <ScenarioDetailCard scenario={scenario.data} isLoading={scenario.isFetching} />
          <OpenRouterModelSelect
            value={llmModel}
            onChange={setLlmModel}
            disabled={!scenarioId || isRunningAll}
          />
          <Button
            leftSection={<IconPlayerPlay size={16} />}
            onClick={() => void runAll()}
            loading={isRunningAll}
            disabled={!scenarioId}
          >
            Run All Runners
          </Button>
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 8 }}>
        <Card withBorder padding="md" radius="md">
          <ScrollArea type="auto" offsetScrollbars>
            <ComparisonTable
              runners={runners.data ?? []}
              results={results}
              errors={runnerErrors}
              runningRunner={runningRunner}
              onSelect={setSelected}
            />
          </ScrollArea>
        </Card>
        {scenarioId && (
          <Card withBorder padding="md" radius="md" mt="md">
            {recommendation.data ? (
              <Stack gap="xs">
                <Group gap={4}>
                  <Text fw={600}>Recommendation after comparison</Text>
                  <HelpIcon label="This summarizes which runner or blended strategy looks best after comparing recorded evidence for this scenario." />
                </Group>
                <Text size="sm">{recommendation.data.summary}</Text>
                <Badge variant="light">
                  {recommendation.data.strategy} · complexity{' '}
                  {recommendation.data.operational_complexity}/5
                </Badge>
              </Stack>
            ) : (
              <Text c="dimmed" ta="center">
                Run all runners or add demo data to generate a recommendation.
              </Text>
            )}
          </Card>
        )}
      </Grid.Col>
      <Modal
        opened={selected !== null}
        onClose={() => setSelected(null)}
        title="Run details"
        size="80%"
        scrollAreaComponent={ScrollArea.Autosize}
        styles={{ body: { overflowX: 'hidden' } }}
      >
        {selected && (
          <RunResultPanel
            key={selected.run_id}
            result={selected}
            isPending={false}
            error={null}
            onUpdate={handleResultUpdate}
          />
        )}
      </Modal>
    </Grid>
  );
}

export default ComparePage;
