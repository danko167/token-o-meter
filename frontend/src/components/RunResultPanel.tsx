import { useState, type ReactNode } from 'react';
import {
  Accordion,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  Checkbox,
  Code,
  Grid,
  Group,
  Loader,
  Rating,
  RingProgress,
  ScrollArea,
  Stack,
  Table,
  Text,
  Textarea,
  ThemeIcon,
  Timeline,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import {
  IconAlertTriangle,
  IconArrowRight,
  IconCheck,
  IconClock,
  IconRoute,
  IconX,
} from '@tabler/icons-react';
import { useSubmitDecision, useSubmitHumanEvaluation } from '../hooks/useRuns';
import { CostComparisonPopover } from './CostComparisonPopover';
import { HelpIcon } from './HelpIcon';
import { scoreColor, statusColor } from '../lib/runnerLevels';
import type { ApiError } from '../api/client';
import type { DecisionValue, RunResult } from '../api/types';

const wrapAnywhereStyle = {
  minWidth: 0,
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
} as const;

const codeBlockStyle = {
  maxWidth: '100%',
  overflowX: 'hidden',
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
} as const;

interface Props {
  result?: RunResult;
  isPending: boolean;
  error: ApiError | null;
  onUpdate?: (result: RunResult) => void;
}

function parseScore(value: number | string) {
  return typeof value === 'number' ? value : Number(value);
}

function validateScore(value: number | string) {
  const score = parseScore(value);

  return Number.isFinite(score) && score >= 1 && score <= 5
    ? null
    : 'Score must be between 1 and 5.';
}

function StatItem({
  help,
  label,
  value,
  extra,
}: {
  help?: string;
  label: string;
  value: string;
  extra?: ReactNode;
}) {
  return (
    <Stack gap={0} align="center">
      <Text size="lg" fw={600}>
        {value}
      </Text>
      <Group gap={3} justify="center">
        <Text size="xs" c="dimmed">
          {label}
        </Text>
        {help && <HelpIcon label={help} />}
      </Group>
      {extra}
    </Stack>
  );
}

function traceColor(kind: string) {
  switch (kind) {
    case 'error':
      return 'red';
    case 'checkpoint':
    case 'decision':
      return 'yellow';
    case 'tool':
      return 'violet';
    case 'evaluation':
      return 'green';
    default:
      return 'blue';
  }
}

function CheckpointTriggers({ details }: { details: Record<string, unknown> }) {
  const triggers = details.triggers;

  if (Array.isArray(triggers) && triggers.length > 0) {
    return (
      <Stack gap="xs">
        {triggers.map((trigger, index) => {
          const t = trigger as Record<string, unknown>;
          const kind = typeof t.kind === 'string' ? t.kind : 'trigger';
          const reason = typeof t.reason === 'string' ? t.reason : '';

          return (
            <Group key={`${kind}-${index}`} gap="xs" wrap="wrap" align="flex-start">
              <Badge color="yellow" variant="light">
                {kind.replace(/_/g, ' ')}
              </Badge>
              <Text size="sm" style={wrapAnywhereStyle}>
                {reason}
              </Text>
            </Group>
          );
        })}
      </Stack>
    );
  }

  if (Object.keys(details).length === 0) {
    return null;
  }

  return (
    <Code block style={codeBlockStyle}>
      {JSON.stringify(details, null, 2)}
    </Code>
  );
}

function graphNodes(result: RunResult) {
  return result.trace.events
    .map((event) => ({
      name: typeof event.details.node === 'string' ? event.details.node : null,
      duration_ms: event.duration_ms,
      prompt_tokens: event.prompt_tokens,
      completion_tokens: event.completion_tokens,
      estimated_cost_usd: event.estimated_cost_usd,
    }))
    .filter(
      (
        event,
      ): event is {
        name: string;
        duration_ms: number | null;
        prompt_tokens: number;
        completion_tokens: number;
        estimated_cost_usd: number;
      } => event.name !== null,
    );
}

function RunStats({ result }: { result: RunResult }) {
  return (
    <Group grow wrap="wrap">
      <StatItem
        help="Total wall-clock time for this run, including model calls, tools, evaluation, and checkpoint handling."
        label="Duration"
        value={`${result.metrics.duration_ms} ms`}
      />
      <StatItem
        help="Input tokens sent to the model. Rules and workflow runners never call a model, so this is zero."
        label="Prompt tokens"
        value={String(result.metrics.prompt_tokens)}
      />
      <StatItem
        help="Output tokens returned by the model. More generated text usually means higher cost and latency."
        label="Completion tokens"
        value={String(result.metrics.completion_tokens)}
      />
      <StatItem
        help="Estimated model cost from token usage and the selected model's pricing. Deterministic runners should be near zero."
        label="Est. cost"
        value={`$${result.metrics.estimated_cost_usd.toFixed(4)}`}
        extra={
          <CostComparisonPopover
            promptTokens={result.metrics.prompt_tokens}
            completionTokens={result.metrics.completion_tokens}
          />
        }
      />
      <StatItem
        help="How many times the runner retried because it could not parse or validate a model response."
        label="Retries"
        value={String(result.metrics.retries)}
      />
    </Group>
  );
}

function ToolCallsSection({ result }: { result: RunResult }) {
  if (result.metrics.tool_calls.length === 0) {
    return null;
  }

  return (
    <Box>
      <Group gap={4} mb={4}>
        <Text size="sm" fw={500}>
          Tool calls
        </Text>
        <HelpIcon label="External lookups the runner performed, such as order lookup, policy search, or reading a repository file." />
      </Group>

      <ScrollArea type="auto" offsetScrollbars style={{ maxWidth: '100%' }}>
        <Table striped style={{ tableLayout: 'fixed', width: '100%' }}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={{ width: 120 }}>Tool</Table.Th>
              <Table.Th style={{ width: 90 }}>Duration</Table.Th>
              <Table.Th style={{ width: 70 }}>Found</Table.Th>
              <Table.Th>Details</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {result.metrics.tool_calls.map((call, index) => (
              <Table.Tr key={`${call.name}-${index}`}>
                <Table.Td style={wrapAnywhereStyle}>{call.name}</Table.Td>
                <Table.Td>{call.duration_ms} ms</Table.Td>
                <Table.Td>{call.found === null ? '-' : call.found ? 'yes' : 'no'}</Table.Td>
                <Table.Td style={wrapAnywhereStyle}>
                  <Code style={wrapAnywhereStyle}>{JSON.stringify(call.details)}</Code>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </Box>
  );
}

function OutputSection({ result }: { result: RunResult }) {
  if (Object.keys(result.output).length === 0) {
    return null;
  }

  return (
    <Box>
      <Group gap={4} mb={4}>
        <Text size="sm" fw={500}>
          Output
        </Text>
        <HelpIcon label="The structured result produced by the runner before evaluation scoring." />
      </Group>

      <Code block style={codeBlockStyle}>
        {JSON.stringify(result.output, null, 2)}
      </Code>
    </Box>
  );
}

function ActionsSection({ result }: { result: RunResult }) {
  if (result.actions.length === 0) {
    return null;
  }

  return (
    <Box>
      <Group gap={4} mb={4}>
        <Text size="sm" fw={500}>
          Recommended action(s)
        </Text>
        <HelpIcon label="Operational actions the runner proposes. Human-checkpoint runners may pause before high-risk actions are taken." />
      </Group>

      <Group gap="xs" style={wrapAnywhereStyle}>
        {result.actions.map((action) => (
          <Badge
            key={action}
            variant="outline"
            leftSection={<IconArrowRight size={12} />}
            style={wrapAnywhereStyle}
          >
            {action}
          </Badge>
        ))}
      </Group>
    </Box>
  );
}

function RunTrace({ result }: { result: RunResult }) {
  const nodes = graphNodes(result);

  if (result.trace.events.length === 0) {
    return null;
  }

  return (
    <Box>
      <Group gap={4} mb={8}>
        <Text size="sm" fw={500}>
          Trace
        </Text>
        <HelpIcon label="Timeline of what happened during the run: request, graph nodes, tools, checkpoints, decisions, errors, and evaluation." />
      </Group>

      {nodes.length > 0 && (
        <ScrollArea type="auto" offsetScrollbars mb="sm" style={{ maxWidth: '100%' }}>
          <Group gap="xs" wrap="wrap">
            {nodes.map((node, index) => (
              <Group key={`${node.name}-${index}`} gap="xs" wrap="nowrap">
                <Stack
                  gap={2}
                  p="xs"
                  style={{
                    border: '1px solid var(--mantine-color-gray-3)',
                    borderRadius: 8,
                    minWidth: 132,
                  }}
                >
                  <Text size="sm" fw={600} style={wrapAnywhereStyle}>
                    {node.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {node.duration_ms ?? 0} ms
                    {node.prompt_tokens || node.completion_tokens
                      ? ` · ${node.prompt_tokens + node.completion_tokens} tokens`
                      : ''}
                  </Text>
                </Stack>
                {index < nodes.length - 1 && <IconArrowRight size={16} />}
              </Group>
            ))}
          </Group>
        </ScrollArea>
      )}

      <Timeline active={result.trace.events.length - 1} bulletSize={22} lineWidth={2}>
        {result.trace.events.map((event, index) => (
          <Timeline.Item
            key={`${event.timestamp}-${event.name}-${index}`}
            color={traceColor(event.kind)}
            bullet={<IconRoute size={12} />}
            title={
              <Group gap="xs" wrap="wrap" style={wrapAnywhereStyle}>
                <Text size="sm" fw={500} style={wrapAnywhereStyle}>
                  {event.name}
                </Text>
                <Badge size="xs" variant="light" color={traceColor(event.kind)}>
                  {event.kind}
                </Badge>
              </Group>
            }
          >
            <Stack gap={4}>
              <Text size="xs" c="dimmed">
                {new Date(event.timestamp).toLocaleTimeString()}
                {event.duration_ms !== null ? ` · ${event.duration_ms} ms` : ''}
                {event.prompt_tokens || event.completion_tokens
                  ? ` · ${event.prompt_tokens}/${event.completion_tokens} tokens`
                  : ''}
                {event.estimated_cost_usd ? ` · $${event.estimated_cost_usd.toFixed(6)}` : ''}
              </Text>

              {Object.keys(event.details).length > 0 && (
                <Accordion variant="contained" radius="md">
                  <Accordion.Item value="details">
                    <Accordion.Control>
                      <Text size="xs">Details</Text>
                    </Accordion.Control>
                    <Accordion.Panel>
                      <Code block style={codeBlockStyle}>
                        {JSON.stringify(event.details, null, 2)}
                      </Code>
                    </Accordion.Panel>
                  </Accordion.Item>
                </Accordion>
              )}
            </Stack>
          </Timeline.Item>
        ))}
      </Timeline>
    </Box>
  );
}

function PendingApprovalSection({
  errorMessage,
  isPending,
  onDecision,
  pendingDecision,
  result,
}: {
  errorMessage?: string;
  isPending: boolean;
  onDecision: (decision: DecisionValue) => void;
  pendingDecision?: DecisionValue;
  result: RunResult;
}) {
  if (!result.pending_approval) {
    return null;
  }

  return (
    <Alert
      color="yellow"
      icon={<IconClock size={18} />}
      title={
        <Group gap={4} wrap="nowrap">
          Waiting for human approval
          <HelpIcon label="Approve lets the runner take its proposed action. Reject blocks that action and escalates the case for human review instead." />
        </Group>
      }
    >
      <Stack gap="sm">
        {result.pending_approval.reason && (
          <Text size="sm" style={wrapAnywhereStyle}>
            {result.pending_approval.reason}
          </Text>
        )}

        <Group gap="xs" style={wrapAnywhereStyle}>
          <Text size="sm" fw={500}>
            Proposed action:
          </Text>
          <Badge
            variant="outline"
            leftSection={<IconArrowRight size={12} />}
            style={wrapAnywhereStyle}
          >
            {result.pending_approval.action}
          </Badge>
        </Group>

        <CheckpointTriggers details={result.pending_approval.details} />

        {errorMessage && (
          <Text size="sm" c="red">
            {errorMessage}
          </Text>
        )}

        <Group gap="xs">
          <Button
            color="green"
            leftSection={<IconCheck size={16} />}
            loading={isPending && pendingDecision === 'approve'}
            disabled={isPending}
            onClick={() => onDecision('approve')}
          >
            Approve
          </Button>
          <Button
            color="red"
            variant="outline"
            leftSection={<IconX size={16} />}
            loading={isPending && pendingDecision === 'reject'}
            disabled={isPending}
            onClick={() => onDecision('reject')}
          >
            Reject
          </Button>
        </Group>
      </Stack>
    </Alert>
  );
}

function EvaluationDisplay({ result }: { result: RunResult }) {
  if (!result.evaluation) {
    return null;
  }

  return (
    <Card withBorder radius="md" padding="md">
      <Group align="flex-start" gap="lg" wrap="wrap">
        <RingProgress
          size={90}
          thickness={8}
          roundCaps
          sections={[
            {
              value: result.evaluation.score,
              color: scoreColor(result.evaluation.score),
            },
          ]}
          label={
            <Text fw={700} ta="center" size="sm">
              {result.evaluation.score}
            </Text>
          }
        />

        <Stack gap={4} flex={1} style={wrapAnywhereStyle}>
          <Group gap={4}>
            <Text size="sm" fw={600}>
              Evaluation checks
            </Text>
            <HelpIcon label="Checks compare the runner output against expected fields, required fields, forbidden actions, and optional judge results." />
          </Group>

          {result.evaluation.checks.map((check) => (
            <Group key={check.name} gap="xs" wrap="wrap" align="flex-start">
              <ThemeIcon
                color={check.passed ? 'green' : 'red'}
                variant="light"
                size="sm"
                radius="xl"
              >
                {check.passed ? <IconCheck size={12} /> : <IconX size={12} />}
              </ThemeIcon>

              <Stack gap={0} style={wrapAnywhereStyle}>
                <Text size="sm" style={wrapAnywhereStyle}>
                  {check.name}
                </Text>
                <Text size="xs" c="dimmed" style={wrapAnywhereStyle}>
                  {check.detail}
                </Text>
              </Stack>
            </Group>
          ))}
        </Stack>
      </Group>
    </Card>
  );
}

function HumanEvaluationForm({
  errorMessage,
  isPending,
  onSubmit,
  result,
}: {
  errorMessage?: string;
  isPending: boolean;
  onSubmit: (score: number, useful: boolean, correct: boolean, comment: string) => void;
  result: RunResult;
}) {
  const form = useForm({
    initialValues: {
      score: 5 as number | string,
      useful: true,
      correct: true,
      comment: '',
    },
    validate: {
      score: validateScore,
    },
  });

  const humanScoreError = validateScore(form.values.score);

  if (result.status !== 'succeeded') {
    return null;
  }

  const handleSubmit = form.onSubmit((values) => {
    onSubmit(parseScore(values.score), values.useful, values.correct, values.comment);
  });

  return (
    <Card withBorder radius="md" padding="md">
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start">
          <Group gap={4}>
            <Text size="sm" fw={600}>
              Human evaluation
            </Text>
            <HelpIcon label="Manual post-run rating. This is separate from automated scoring and helps capture usefulness or correctness that tests may miss." />
          </Group>

          {result.human_evaluation && (
            <Badge variant="light" color="blue">
              Saved
            </Badge>
          )}
        </Group>

        {result.human_evaluation && (
          <Alert color="blue" variant="light" radius="md">
            <Stack gap={4}>
              <Group gap="xs" wrap="wrap">
                <Badge variant="filled" color="blue">
                  {result.human_evaluation.score}/5
                </Badge>
                <Badge variant="outline">
                  Useful: {result.human_evaluation.useful ? 'yes' : 'no'}
                </Badge>
                <Badge variant="outline">
                  Correct: {result.human_evaluation.correct ? 'yes' : 'no'}
                </Badge>
              </Group>

              {result.human_evaluation.comment && (
                <Text size="sm" c="dimmed" style={wrapAnywhereStyle}>
                  {result.human_evaluation.comment}
                </Text>
              )}
            </Stack>
          </Alert>
        )}

        <Stack gap={4}>
          <Group justify="space-between">
            <Text size="sm" fw={500}>
              Score
            </Text>
            <Badge variant="light">{parseScore(form.values.score)}/5</Badge>
          </Group>

          <Rating
            count={5}
            value={parseScore(form.values.score)}
            onChange={(value) => form.setFieldValue('score', value)}
          />

          <Text size="xs" c="dimmed">
            Rate this run from 1 to 5.
          </Text>

          {humanScoreError && (
            <Text size="xs" c="red">
              {humanScoreError}
            </Text>
          )}
        </Stack>

        <Group grow>
          <Checkbox label="Useful" {...form.getInputProps('useful', { type: 'checkbox' })} />
          <Checkbox label="Correct" {...form.getInputProps('correct', { type: 'checkbox' })} />
        </Group>

        <Textarea
          label="Comment"
          placeholder="What worked, what failed, or what should improve?"
          autosize
          minRows={2}
          {...form.getInputProps('comment')}
        />

        {errorMessage && (
          <Alert color="red" variant="light" radius="md">
            {errorMessage}
          </Alert>
        )}

        <Button
          fullWidth
          variant="light"
          onClick={() => handleSubmit()}
          loading={isPending}
          disabled={isPending || Boolean(humanScoreError)}
        >
          Save human evaluation
        </Button>
      </Stack>
    </Card>
  );
}

export function RunResultPanel({ result, isPending, error, onUpdate }: Props) {
  const [resumed, setResumed] = useState<RunResult | null>(null);
  const submitDecision = useSubmitDecision();
  const submitHumanEvaluation = useSubmitHumanEvaluation();

  if (isPending) {
    return (
      <Card withBorder padding="md" radius="md">
        <Group justify="center" py="xl" gap="sm">
          <Loader size="sm" />
          <Text c="dimmed">Running...</Text>
        </Group>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert color="red" icon={<IconAlertTriangle size={18} />} title="Request failed">
        {error.message}
      </Alert>
    );
  }

  if (!result) {
    return (
      <Card withBorder padding="md" radius="md">
        <Text c="dimmed">Run a scenario to see results here.</Text>
      </Card>
    );
  }

  const display = resumed ?? result;

  const handleDecision = (decision: DecisionValue) => {
    submitDecision.mutate(
      { runId: display.run_id, decision },
      {
        onSuccess: (updated) => {
          setResumed(updated);
          onUpdate?.(updated);
        },
      },
    );
  };

  const handleHumanEvaluation = (
    score: number,
    useful: boolean,
    correct: boolean,
    comment: string,
  ) => {
    submitHumanEvaluation.mutate(
      {
        runId: display.run_id,
        evaluation: {
          score,
          useful,
          correct,
          comment,
        },
      },
      {
        onSuccess: (updated) => {
          setResumed(updated);
          onUpdate?.(updated);
        },
      },
    );
  };

  return (
    <Card withBorder padding="md" radius="md" style={{ maxWidth: '100%', overflowX: 'hidden' }}>
      <Stack gap="md">
        <Group justify="space-between" wrap="wrap" style={wrapAnywhereStyle}>
          <Group gap="xs" style={wrapAnywhereStyle}>
            <Badge color={statusColor(display.status)} variant="filled">
              {display.status}
            </Badge>
            <Text size="sm" c="dimmed" style={wrapAnywhereStyle}>
              {display.runner} · {display.scenario_id}
            </Text>
          </Group>

          <Text size="xs" c="dimmed" ff="monospace" style={wrapAnywhereStyle}>
            {display.run_id}
          </Text>
        </Group>

        {display.error && (
          <Alert color="red" icon={<IconAlertTriangle size={18} />} title="Runner error">
            {display.error}
          </Alert>
        )}

        <RunStats result={display} />

        <ToolCallsSection result={display} />

        <Grid>
          <Grid.Col span={{ base: 12, md: 7 }}>
            <OutputSection result={display} />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 5 }}>
            <ActionsSection result={display} />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 7 }}>
            <RunTrace result={display} />
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 5 }}>
            <Stack gap="md">
              <EvaluationDisplay result={display} />

              <HumanEvaluationForm
                result={display}
                errorMessage={submitHumanEvaluation.error?.message}
                isPending={submitHumanEvaluation.isPending}
                onSubmit={handleHumanEvaluation}
              />
            </Stack>
          </Grid.Col>
        </Grid>

        <PendingApprovalSection
          result={display}
          errorMessage={submitDecision.error?.message}
          isPending={submitDecision.isPending}
          pendingDecision={submitDecision.variables?.decision}
          onDecision={handleDecision}
        />
      </Stack>
    </Card>
  );
}
