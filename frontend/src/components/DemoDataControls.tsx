import { useState } from 'react';
import {
  ActionIcon,
  Alert,
  Button,
  Checkbox,
  Divider,
  Grid,
  Group,
  Loader,
  Modal,
  Progress,
  Slider,
  SimpleGrid,
  Stack,
  Text,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import {
  IconDatabase,
  IconDatabaseImport,
  IconMinus,
  IconPlayerPlay,
  IconPlus,
  IconTrash,
} from '@tabler/icons-react';
import { useNarrativeLoader } from '@danko167/narrative-loader';
import { API_BASE_URL } from '../api/client';
import { notifyError, notifySuccess, notifyWarning } from '../lib/notify';
import type { DemoDataResult, DemoExecutionStatus, ScenarioFamily } from '../api/types';
import { scenarioFamilyOptions } from '../lib/scenarioFamilies';
import { BrandSignal } from './BrandSignal';
import { OpenRouterModelSelect } from './OpenRouterModelSelect';
import {
  useAddDemoData,
  useDeleteDemoData,
  useDemoExecutionStatus,
  useExecuteDemoData,
} from '../hooks/useDemoData';

const DEMO_SCENARIO_FAMILY_OPTIONS = scenarioFamilyOptions.filter(
  (option): option is { value: ScenarioFamily; label: string } => option.value !== 'all',
);
const ALL_DEMO_SCENARIO_FAMILIES = DEMO_SCENARIO_FAMILY_OPTIONS.map((option) => option.value);

export function DemoDataControls() {
  const [opened, { open, close }] = useDisclosure(false);
  const [llmModel, setLlmModel] = useState<string | null>(null);
  const [runsPerRunnerPerScenario, setRunsPerRunnerPerScenario] = useState<number | string>(2);
  const [scenarioFamilies, setScenarioFamilies] = useState<ScenarioFamily[]>(
    ALL_DEMO_SCENARIO_FAMILIES,
  );
  const addDemoData = useAddDemoData();
  const executeDemoData = useExecuteDemoData();
  const deleteDemoData = useDeleteDemoData();
  const isWorking =
    addDemoData.isPending || executeDemoData.isPending || deleteDemoData.isPending;
  const error =
    addDemoData.error ?? executeDemoData.error ?? deleteDemoData.error;
  const progressMode = addDemoData.isPending
    ? 'Simulated history progress'
    : 'Execution progress';
  const shouldPollDemoProgress = opened && (addDemoData.isPending || executeDemoData.isPending);

  const demoProgress = useNarrativeLoader({
    loading: shouldPollDemoProgress,
    source: shouldPollDemoProgress ? `${API_BASE_URL}/demo-data/execute/status` : undefined,
    pollInterval: 1000,
    variant: 'analysis',
    getMessage: (data) => (data as DemoExecutionStatus).message,
    stopWhen: (data) => {
      const status = data as DemoExecutionStatus;
      return status.done || !status.running;
    },
    doneMessage: 'Demo data ready',
    doneDuration: 1000,
  });
  const executionStatus = useDemoExecutionStatus(shouldPollDemoProgress);
  const demoRunCount =
    typeof runsPerRunnerPerScenario === 'number' ? runsPerRunnerPerScenario : 2;
  const progressTotal = executionStatus.data?.total ?? 0;
  const progressCurrent = executionStatus.data?.current ?? 0;
  const progressValue =
    progressTotal > 0 ? Math.min(100, Math.round((progressCurrent / progressTotal) * 100)) : 0;

  const setDemoRunCount = (value: number) => {
    setRunsPerRunnerPerScenario(Math.max(1, Math.min(20, value)));
  };

  const setDemoScenarioFamilies = (values: string[]) => {
    if (values.length === 0) {
      return;
    }
    setScenarioFamilies(values as ScenarioFamily[]);
  };

  const handleAddSeeded = () => {
    const count = demoRunCount;
    addDemoData.mutate({ runsPerRunnerPerScenario: count, scenarioFamilies }, {
      onSuccess: (result: DemoDataResult) => {
        close();
        notifySuccess({
          title: 'Demo data added',
          message: `${result.created} demo run${result.created === 1 ? '' : 's'} added.`,
        });
      },
      onError: (err) => notifyError('Could not add demo data', err),
    });
  };

  const handleExecute = () => {
    const count = demoRunCount;
    executeDemoData.mutate({ llmModel, runsPerRunnerPerScenario: count, scenarioFamilies }, {
      onSuccess: (result: DemoDataResult) => {
        close();
        if (result.skipped > 0) {
          notifyWarning({
            title: 'Some demo runs were skipped',
            message: `${result.skipped} of ${result.created} runs were skipped because the LLM provider rate-limited requests. Try again later, choose another model, or add provider credits.`,
          });
        } else {
          notifySuccess({
            title: 'Demo data executed',
            message: `${result.created} demo run${result.created === 1 ? '' : 's'} created by running scenarios.`,
          });
        }
      },
      onError: (err) => notifyError('Could not execute demo data', err),
    });
  };

  const handleDelete = () => {
    deleteDemoData.mutate(undefined, {
      onSuccess: (result: DemoDataResult) => {
        close();
        notifySuccess({
          title: 'Demo data deleted',
          message: `${result.deleted} demo run${result.deleted === 1 ? '' : 's'} deleted.`,
        });
      },
      onError: (err) => notifyError('Could not delete demo data', err),
    });
  };

  return (
    <>
      <Button
        size="xs"
        variant="light"
        leftSection={<IconDatabase size={14} />}
        rightSection={isWorking ? <Loader size={12} /> : null}
        onClick={open}
      >
        Demo data
      </Button>

      <Modal
        opened={opened}
        onClose={close}
        title={
          <Stack gap={6}>
            <span>Demo data</span>
            <BrandSignal className="brandSignal-modal" />
          </Stack>
        }
        size="lg"
      >
        <Stack gap="md">
          <Stack gap={6}>
            <Group justify="space-between" align="center">
              <Stack gap={0}>
                <Text size="sm" fw={500}>
                  Runs per runner per scenario
                </Text>
                <Text size="xs" c="dimmed">
                  Applied to every scenario and every runner for either add option.
                </Text>
              </Stack>
              <Group gap={4} wrap="nowrap">
                <ActionIcon
                  variant="light"
                  size="sm"
                  disabled={isWorking || demoRunCount <= 1}
                  onClick={() => setDemoRunCount(demoRunCount - 1)}
                  aria-label="Decrease runs per runner per scenario"
                >
                  <IconMinus size={14} />
                </ActionIcon>
                <Text size="sm" fw={700} ff="monospace" miw={24} ta="center">
                  {demoRunCount}
                </Text>
                <ActionIcon
                  variant="light"
                  size="sm"
                  disabled={isWorking || demoRunCount >= 20}
                  onClick={() => setDemoRunCount(demoRunCount + 1)}
                  aria-label="Increase runs per runner per scenario"
                >
                  <IconPlus size={14} />
                </ActionIcon>
              </Group>
            </Group>
            <Slider
              min={1}
              max={20}
              step={1}
              value={demoRunCount}
              disabled={isWorking}
              onChange={setDemoRunCount}
              marks={[
                { value: 1, label: '1' },
                { value: 10, label: '10' },
                { value: 20, label: '20' },
              ]}
            />
          </Stack>

          <Stack gap={8} mt="md">
            <Stack gap={0}>
              <Text size="sm" fw={500}>
                Scenario families
              </Text>
              <Text size="xs" c="dimmed">
                Applied to both demo data add options.
              </Text>
            </Stack>

            <Checkbox.Group
              value={scenarioFamilies}
              onChange={setDemoScenarioFamilies}
            >
              <SimpleGrid cols={{ base: 1, sm: 3 }} spacing={10}>
                {DEMO_SCENARIO_FAMILY_OPTIONS.map((option) => (
                  <Checkbox
                    size="xs"
                    key={option.value}
                    value={option.value}
                    label={option.label}
                    disabled={
                      isWorking ||
                      (scenarioFamilies.length === 1 && scenarioFamilies[0] === option.value)
                    }
                  />
                ))}
              </SimpleGrid>
            </Checkbox.Group>
          </Stack>

          <Divider mt="xs" />

          <Grid gutter="md">
            <Grid.Col span={{ base: 12, sm: 6 }}>
              <Stack gap="xs" h="100%" justify="space-between">
                <Stack gap={4}>
                  <Text size="sm" fw={600}>
                    Simulated run history
                  </Text>
                  <Text size="xs" c="dimmed">
                    Fast, deterministic, no LLM calls. Seeds representative run history
                    for recommendations, history, metrics, traces, and checkpoints.
                  </Text>
                </Stack>
                <Button
                  fullWidth
                  justify="flex-start"
                  variant="light"
                  leftSection={<IconDatabaseImport size={16} />}
                  loading={addDemoData.isPending}
                  disabled={isWorking && !addDemoData.isPending}
                  onClick={handleAddSeeded}
                >
                  Add simulated run history
                </Button>
              </Stack>
            </Grid.Col>

            <Grid.Col span={{ base: 12, sm: 6 }}>
              <Stack gap="xs">
                <Stack gap={4}>
                  <Text size="sm" fw={600}>
                    Execute scenarios
                  </Text>
                  <Text size="xs" c="dimmed">
                    Runs the scenarios through the actual runners. LLM-backed runners may
                    use tokens and can fail if model access is unavailable.
                  </Text>
                </Stack>
                <OpenRouterModelSelect
                  value={llmModel}
                  onChange={setLlmModel}
                  disabled={isWorking}
                />
                <Button
                  fullWidth
                  justify="flex-start"
                  variant="light"
                  color="blue"
                  leftSection={<IconPlayerPlay size={16} />}
                  loading={executeDemoData.isPending}
                  disabled={isWorking && !executeDemoData.isPending}
                  onClick={handleExecute}
                >
                  {executeDemoData.isPending
                    ? 'Executing scenarios/runners'
                    : 'Add by executing scenarios/runners'}
                </Button>

              </Stack>
            </Grid.Col>
          </Grid>
          {demoProgress.visible ? (
            <Alert color="blue" variant="light" p="sm">
              <Stack gap={6}>
                <Group justify="space-between" gap="xs">
                  <Text size="xs" fw={600}>
                    {progressMode}
                  </Text>
                  {progressTotal > 0 ? (
                    <Text size="xs" c="dimmed" ff="monospace">
                      {progressCurrent} / {progressTotal}
                    </Text>
                  ) : null}
                </Group>
                <Progress
                  className="demoProgressSignal"
                  value={progressValue}
                  size="sm"
                  radius="xl"
                  animated
                />
                <Text size="xs" c="dimmed" style={{ overflowWrap: 'anywhere' }}>
                  {demoProgress.text}
                </Text>
              </Stack>
            </Alert>
          ) : null}
          <Button
            fullWidth
            justify="center"
            color="red"
            variant="subtle"
            leftSection={<IconTrash size={16} />}
            loading={deleteDemoData.isPending}
            disabled={isWorking && !deleteDemoData.isPending}
            onClick={handleDelete}
          >
            Delete demo data
          </Button>

          {error && (
            <Alert color="red" variant="light">
              {error instanceof Error ? error.message : 'Demo data action failed.'}
            </Alert>
          )}
        </Stack>
      </Modal>
    </>
  );
}
