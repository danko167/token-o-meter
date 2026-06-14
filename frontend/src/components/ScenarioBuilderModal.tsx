import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Group,
  Modal,
  NumberInput,
  ScrollArea,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useCreateScenario, useDeleteScenario, useScenarios } from '../hooks/useScenarios';
import { HelpIcon } from './HelpIcon';
import { scenarioFamilyOptions } from '../lib/scenarioFamilies';
import type { Scenario, ScenarioCreate, ScenarioFamily } from '../api/types';

interface Props {
  opened: boolean;
  defaultFamily: ScenarioFamily;
  onClose: () => void;
  onCreated: (scenario: Scenario) => void;
}

const DEFAULT_EXPECTED = '{\n  "intent": "billing_issue"\n}';

function initialScenarioFormValues(family: ScenarioFamily) {
  return {
    family,
    name: '',
    description: '',
    input: '',
    expected: DEFAULT_EXPECTED,
    requiredFields: '',
    forbiddenActions: '',
    confidenceThreshold: '' as number | string,
  };
}

export function ScenarioBuilderModal({ opened, defaultFamily, onClose, onCreated }: Props) {
  const wasOpened = useRef(opened);
  const [formError, setFormError] = useState<string | null>(null);
  const form = useForm({
    initialValues: initialScenarioFormValues(defaultFamily),
  });

  const scenarios = useScenarios();
  const createScenario = useCreateScenario();
  const deleteScenario = useDeleteScenario();

  useEffect(() => {
    if (opened && !wasOpened.current) {
      form.setFieldValue('family', defaultFamily);
    }
    wasOpened.current = opened;
  }, [defaultFamily, form, opened]);

  const filtered = useMemo(
    () => (scenarios.data ?? []).filter((scenario) => scenario.family === form.values.family),
    [form.values.family, scenarios.data],
  );

  const handleCreate = () => {
    setFormError(null);
    let parsedExpected: Record<string, unknown>;
    try {
      parsedExpected = JSON.parse(form.values.expected) as Record<string, unknown>;
      if (
        typeof parsedExpected !== 'object' ||
        Array.isArray(parsedExpected) ||
        parsedExpected === null
      ) {
        throw new Error('Expected output must be a JSON object.');
      }
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Expected output must be valid JSON.');
      return;
    }

    const confidenceThreshold =
      form.values.confidenceThreshold === ''
        ? null
        : Number(form.values.confidenceThreshold);
    if (
      confidenceThreshold !== null &&
      (!Number.isFinite(confidenceThreshold) ||
        confidenceThreshold < 0 ||
        confidenceThreshold > 1)
    ) {
      setFormError('Confidence threshold must be between 0 and 1.');
      return;
    }

    const payload: ScenarioCreate = {
      name: form.values.name,
      description: form.values.description,
      family: form.values.family,
      input: form.values.input,
      expected: parsedExpected,
      required_fields: splitList(form.values.requiredFields),
      forbidden_actions: splitList(form.values.forbiddenActions),
      confidence_threshold: confidenceThreshold,
    };

    createScenario.mutate(payload, {
      onSuccess: (scenario) => {
        form.setValues(initialScenarioFormValues(form.values.family));
        setFormError(null);
        onCreated(scenario);
        onClose();
      },
      onError: (error) => {
        setFormError(error.message);
      },
    });
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Add Scenario"
      size="80%"
      scrollAreaComponent={ScrollArea.Autosize}
    >
      <Stack>
        <Alert color="blue" variant="light">
          Add benchmark cases inside the existing families. New scenarios are stored in
          SQLite and can be run immediately.
        </Alert>

        <Stack gap="sm">
          <Group gap={4}>
            <Title order={5}>Create Scenario</Title>
            <HelpIcon label="Use this when the built-in scenarios do not represent your real cases. The new scenario becomes part of the benchmark immediately." />
          </Group>
          <Select
            label={
              <Group gap={4}>
                Scenario family
                <HelpIcon label="Pick the existing task type whose runners and evaluator should handle this scenario." />
              </Group>
            }
            data={scenarioFamilyOptions.filter((option) => option.value !== 'all')}
            value={form.values.family}
            onChange={(value) => form.setFieldValue('family', (value ?? defaultFamily) as ScenarioFamily)}
          />
          <TextInput
            label="Name"
            placeholder="VIP billing escalation"
            {...form.getInputProps('name')}
          />
          <TextInput
            label="Description"
            placeholder="What this scenario is meant to test"
            {...form.getInputProps('description')}
          />
          <Textarea
            label={
              <Group gap={4}>
                Input
                <HelpIcon label="This is the exact text or diff that every runner receives. Keep it realistic, because recommendations are only as good as the scenarios." />
              </Group>
            }
            minRows={4}
            autosize
            {...form.getInputProps('input')}
          />
          <Textarea
            label={
              <Group gap={4}>
                Expected output JSON
                <HelpIcon label='Fields and values the evaluator should check exactly, such as {"intent":"billing_issue"} or {"verdict":"request_changes"}.' />
              </Group>
            }
            minRows={4}
            autosize
            styles={{ input: { fontFamily: 'monospace' } }}
            {...form.getInputProps('expected')}
          />
          <Group grow align="flex-start">
            <Textarea
              label={
                <Group gap={4}>
                  Required fields
                  <HelpIcon label="Fields that must be present in the runner output, even if you do not care about the exact value." />
                </Group>
              }
              placeholder="order_id, customer_email"
              autosize
              minRows={2}
              {...form.getInputProps('requiredFields')}
            />
            <Textarea
              label={
                <Group gap={4}>
                  Forbidden actions
                  <HelpIcon label="Actions that should never be taken for this scenario. If a runner returns one, evaluation penalizes it." />
                </Group>
              }
              placeholder="refund_customer"
              autosize
              minRows={2}
              {...form.getInputProps('forbiddenActions')}
            />
          </Group>
          <NumberInput
            label={
              <Group gap={4}>
                Confidence threshold
                <HelpIcon label="Optional human-checkpoint threshold from 0 to 1. Runs below this model confidence pause for approval." />
              </Group>
            }
            placeholder="Use default"
            min={0}
            max={1}
            step={0.05}
            decimalScale={2}
            {...form.getInputProps('confidenceThreshold')}
          />
          {(formError || createScenario.error) && (
            <Text c="red" size="sm">
              {formError ?? createScenario.error?.message}
            </Text>
          )}
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={handleCreate}
            loading={createScenario.isPending}
            disabled={!form.values.name.trim() || !form.values.input.trim()}
          >
            Add Scenario
          </Button>
        </Stack>

        <Stack gap="sm">
          <Group gap={4}>
            <Title order={5}>Scenarios In This Family</Title>
            <HelpIcon label="Built-in scenarios come from YAML files. Custom scenarios are stored in SQLite and can be deleted here." />
          </Group>
          <ScrollArea type="auto" offsetScrollbars mah={280}>
            <Table striped highlightOnHover miw={720}>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>ID</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Description</Table.Th>
                  <Table.Th>Actions</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filtered.map((scenario) => (
                  <Table.Tr key={scenario.id}>
                    <Table.Td>{scenario.name}</Table.Td>
                    <Table.Td>
                      <Text size="xs" ff="monospace">
                        {scenario.id}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={scenario.is_custom ? 'green' : 'gray'} variant="light">
                        {scenario.is_custom ? 'custom' : 'built-in'}
                      </Badge>
                    </Table.Td>
                    <Table.Td>{scenario.description}</Table.Td>
                    <Table.Td>
                      {scenario.is_custom && (
                        <Button
                          color="red"
                          variant="subtle"
                          size="xs"
                          leftSection={<IconTrash size={14} />}
                          loading={
                            deleteScenario.isPending && deleteScenario.variables === scenario.id
                          }
                          onClick={() => deleteScenario.mutate(scenario.id)}
                        >
                          Delete
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        </Stack>
      </Stack>
    </Modal>
  );
}

function splitList(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
