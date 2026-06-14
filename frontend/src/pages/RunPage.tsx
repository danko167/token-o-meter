import { useState } from 'react';
import { Alert, Button, Grid, Group, Select, Stack } from '@mantine/core';
import { IconFlask, IconPlayerPlay, IconPlus, IconStack2 } from '@tabler/icons-react';
import { useScenario, useScenarios } from '../hooks/useScenarios';
import { useRunners } from '../hooks/useRunners';
import { useCreateRun } from '../hooks/useRuns';
import { HelpIcon } from '../components/HelpIcon';
import { ScenarioBuilderModal } from '../components/ScenarioBuilderModal';
import { ScenarioDetailCard } from '../components/ScenarioDetailCard';
import { RunnerInfoCard } from '../components/RunnerInfoCard';
import { RunResultPanel } from '../components/RunResultPanel';
import { OpenRouterModelSelect } from '../components/OpenRouterModelSelect';
import { filterScenarios, scenarioFamilyOptions } from '../lib/scenarioFamilies';
import { notifyError, notifySuccess, notifyWarning } from '../lib/notify';
import type { Scenario, ScenarioFamily } from '../api/types';

export function RunPage() {
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [runnerName, setRunnerName] = useState<string | null>(null);
  const [llmModel, setLlmModel] = useState<string | null>(null);
  const [family, setFamily] = useState<ScenarioFamily | 'all'>('all');
  const [scenarioModalOpen, setScenarioModalOpen] = useState(false);

  const scenarios = useScenarios();
  // If the selected scenario was deleted (e.g. via the scenario builder modal),
  // treat the selection as cleared rather than keeping a dangling ID around.
  const selectedScenarioId =
    scenarioId && scenarios.data && !scenarios.data.some((s) => s.id === scenarioId)
      ? null
      : scenarioId;
  const scenario = useScenario(selectedScenarioId);
  const runners = useRunners();
  const createRun = useCreateRun();

  const scenarioOptions = filterScenarios(scenarios.data ?? [], family).map((s) => ({
    value: s.id,
    label: s.name,
  }));
  const runnerOptions = (runners.data ?? []).map((r) => ({
    value: r.name,
    label: `L${r.level} · ${r.name}`,
  }));
  const selectedRunner = runners.data?.find((r) => r.name === runnerName);
  const selectedRunnerUsesLlm = (selectedRunner?.level ?? 0) >= 2;

  const handleRun = () => {
    if (!selectedScenarioId || !runnerName) return;
    createRun.mutate(
      {
        scenario_id: selectedScenarioId,
        runner: runnerName,
        llm_model: selectedRunnerUsesLlm ? llmModel : null,
      },
      {
        onSuccess: (result) => {
          if (result.status === 'succeeded') {
            notifySuccess({
              title: 'Run completed',
              message: `${result.runner} finished ${result.scenario_id}.`,
            });
          } else if (result.status === 'pending_approval') {
            notifyWarning({
              title: 'Run needs human approval',
              message: `${result.runner} paused before taking action.`,
            });
          } else {
            notifyError('Run failed', new Error(result.error ?? 'Runner returned a failed result.'));
          }
        },
        onError: (err) => notifyError('Run request failed', err),
      },
    );
  };

  const handleScenarioCreated = (created: Scenario) => {
    setFamily(created.family);
    setScenarioId(created.id);
  };

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 4 }}>
        <Stack>
          <Alert color="blue" variant="light">
            Pick one scenario and one abstraction level to inspect a single run, including
            metrics, trace, evaluation, and any human checkpoint.
          </Alert>
          <Select
            label={
              <Group gap={4}>
                Scenario family
                <HelpIcon label="A family is a task type with its own output shape and evaluation rules, such as customer support, policy QA, or git diff review." />
              </Group>
            }
            data={scenarioFamilyOptions}
            value={family}
            onChange={(value) => {
              setFamily((value ?? 'all') as ScenarioFamily | 'all');
              setScenarioId(null);
            }}
          />
          <Group align="flex-end" wrap="nowrap">
            <Select
              label={
                <Group gap={4}>
                  Scenario
                  <HelpIcon label="A scenario is one benchmark case: input text plus expected fields and forbidden actions used to score runner output." />
                </Group>
              }
              placeholder="Choose a scenario"
              data={scenarioOptions}
              value={selectedScenarioId}
              onChange={setScenarioId}
              leftSection={<IconFlask size={16} />}
              searchable
              disabled={scenarios.isLoading}
              style={{ flex: 1 }}
            />
            <Button
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={() => setScenarioModalOpen(true)}
            >
              Add
            </Button>
          </Group>
          <ScenarioDetailCard scenario={scenario.data} isLoading={scenario.isFetching} />

          <Select
            label={
              <Group gap={4}>
                Runner (abstraction level)
                <HelpIcon label="A runner is one implementation strategy. Lower levels are simpler and cheaper; higher levels use LLMs, tools, agents, or human checkpoints." />
              </Group>
            }
            placeholder="Choose a runner"
            data={runnerOptions}
            value={runnerName}
            onChange={setRunnerName}
            leftSection={<IconStack2 size={16} />}
            disabled={runners.isLoading}
          />
          <RunnerInfoCard runner={selectedRunner} />
          <OpenRouterModelSelect
            value={llmModel}
            onChange={setLlmModel}
            disabled={!selectedRunnerUsesLlm}
          />

          <Button
            leftSection={<IconPlayerPlay size={16} />}
            onClick={handleRun}
            loading={createRun.isPending}
            disabled={!selectedScenarioId || !runnerName}
          >
            Run
          </Button>
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 8 }}>
        <RunResultPanel
          key={createRun.data?.run_id}
          result={createRun.data}
          isPending={createRun.isPending}
          error={createRun.error}
        />
      </Grid.Col>
      <ScenarioBuilderModal
        opened={scenarioModalOpen}
        defaultFamily={family === 'all' ? 'customer_support' : family}
        onClose={() => setScenarioModalOpen(false)}
        onCreated={handleScenarioCreated}
      />
    </Grid>
  );
}

export default RunPage;
