import { Badge, Group, Loader, Table, Text } from '@mantine/core';
import { IconArrowRight } from '@tabler/icons-react';
import { CostComparisonPopover } from './CostComparisonPopover';
import { HelpIcon } from './HelpIcon';
import { runnerLevelMeta, scoreColor, statusColor } from '../lib/runnerLevels';
import type { RunnerInfo, RunResult } from '../api/types';

interface Props {
  runners: RunnerInfo[];
  results: Record<string, RunResult | undefined>;
  errors: Record<string, string>;
  runningRunner: string | null;
  onSelect: (result: RunResult) => void;
}

export function ComparisonTable({ runners, results, errors, runningRunner, onSelect }: Props) {
  if (runners.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="xl">
        No runners available.
      </Text>
    );
  }

  return (
    <Table highlightOnHover striped>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Runner</Table.Th>
          <Table.Th>Status</Table.Th>
          <Table.Th>
            <HeaderHelp label="Accuracy" help="Automated evaluation score from 0 to 100 based on expected fields, required fields, forbidden actions, and optional judge checks." />
          </Table.Th>
          <Table.Th>
            <HeaderHelp label="Cost" help="Estimated model cost. Rules and workflow runs should normally be zero or near zero." />
          </Table.Th>
          <Table.Th>
            <HeaderHelp label="Tokens" help="Prompt plus completion tokens used by model-backed runners." />
          </Table.Th>
          <Table.Th>
            <HeaderHelp label="Latency" help="Total run duration, including model calls, tool calls, evaluation, and checkpoints." />
          </Table.Th>
          <Table.Th>Action(s)</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {runners.map((runner) => {
          const meta = runnerLevelMeta(runner.level);
          const Icon = meta.icon;
          const result = results[runner.name];
          const error = errors[runner.name];
          const isRunning = runningRunner === runner.name;

          return (
            <Table.Tr
              key={runner.name}
              onClick={result ? () => onSelect(result) : undefined}
              style={{ cursor: result ? 'pointer' : 'default' }}
            >
              <Table.Td>
                <Group gap="xs" wrap="nowrap">
                  <Badge color={meta.color} variant="light" leftSection={<Icon size={12} />}>
                    L{runner.level}
                  </Badge>
                  <Text size="sm">{runner.name}</Text>
                </Group>
              </Table.Td>
              {isRunning ? (
                <Table.Td colSpan={6}>
                  <Group gap="sm">
                    <Loader size="xs" />
                    <Text size="sm" c="dimmed">
                      Running...
                    </Text>
                  </Group>
                </Table.Td>
              ) : result ? (
                <>
                  <Table.Td>
                    <Badge color={statusColor(result.status)} variant="light">
                      {result.status}
                    </Badge>
                    {result.is_demo && (
                      <Badge ml="xs" size="xs" color="gray" variant="light">
                        demo
                      </Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    {result.evaluation ? (
                      <Badge color={scoreColor(result.evaluation.score)} variant="light">
                        {result.evaluation.score}
                      </Badge>
                    ) : (
                      '—'
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      <Text size="sm">${result.metrics.estimated_cost_usd.toFixed(4)}</Text>
                      <CostComparisonPopover
                        promptTokens={result.metrics.prompt_tokens}
                        completionTokens={result.metrics.completion_tokens}
                      />
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    {result.metrics.prompt_tokens + result.metrics.completion_tokens}
                  </Table.Td>
                  <Table.Td>{result.metrics.duration_ms} ms</Table.Td>
                  <Table.Td>
                    {result.actions.length > 0 ? (
                      <Group gap={4}>
                        {result.actions.map((action) => (
                          <Badge
                            key={action}
                            variant="outline"
                            size="sm"
                            leftSection={<IconArrowRight size={10} />}
                          >
                            {action}
                          </Badge>
                        ))}
                      </Group>
                    ) : (
                      '-'
                    )}
                  </Table.Td>
                </>
              ) : error ? (
                <Table.Td colSpan={6}>
                  <Group gap="sm" wrap="nowrap">
                    <Badge color="red" variant="light">
                      Error
                    </Badge>
                    <Text size="sm" c="red" lineClamp={1}>
                      {error}
                    </Text>
                  </Group>
                </Table.Td>
              ) : (
                <>
                  <Table.Td c="dimmed">-</Table.Td>
                  <Table.Td c="dimmed">-</Table.Td>
                  <Table.Td c="dimmed">-</Table.Td>
                  <Table.Td c="dimmed">-</Table.Td>
                  <Table.Td c="dimmed">-</Table.Td>
                  <Table.Td c="dimmed">-</Table.Td>
                </>
              )}
            </Table.Tr>
          );
        })}
      </Table.Tbody>
    </Table>
  );
}

function HeaderHelp({ help, label }: { help: string; label: string }) {
  return (
    <Group gap={4} wrap="nowrap">
      {label}
      <HelpIcon label={help} />
    </Group>
  );
}
