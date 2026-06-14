import {
  ActionIcon,
  Badge,
  Button,
  Collapse,
  Group,
  Loader,
  Popover,
  ScrollArea,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { IconChevronRight, IconGauge } from '@tabler/icons-react';
import { useState } from 'react';
import { useRunUsageSummary } from '../hooks/useRuns';
import type { RunUsageTotals } from '../api/types';

const numberFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 0,
});

function formatTokens(value: number) {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }

  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}k`;
  }

  return numberFormatter.format(value);
}

function formatCost(value: number) {
  if (value === 0) {
    return '$0.00';
  }

  return `$${value >= 1 ? value.toFixed(2) : value.toFixed(6)}`;
}

function TokenUsageCells({ usage }: { usage: RunUsageTotals }) {
  const tokenTotal = usage.input_tokens + usage.output_tokens;

  return (
    <>
      <Table.Td>{usage.runs}</Table.Td>
      <Table.Td>{numberFormatter.format(usage.input_tokens)}</Table.Td>
      <Table.Td>{numberFormatter.format(usage.output_tokens)}</Table.Td>
      <Table.Td>{numberFormatter.format(tokenTotal)}</Table.Td>
      <Table.Td>{formatCost(usage.estimated_cost_usd)}</Table.Td>
    </>
  );
}

function TokenMeterIcon({ size = 'sm' }: { size?: 'sm' | 'lg' }) {
  return (
    <span className={`tokenMeterIcon tokenMeterIcon-${size}`} aria-hidden="true">
      <span />
      <span />
      <span />
      <span />
      <span />
      <span />
    </span>
  );
}

export function TokenMeterPopover() {
  const usageSummary = useRunUsageSummary(true);
  const [expandedRunners, setExpandedRunners] = useState<Set<string>>(new Set());

  if (usageSummary.isLoading || !usageSummary.data) {
    return <Loader size="xs" />;
  }

  const usage = usageSummary.data;
  const totalTokens = usage.totals.input_tokens + usage.totals.output_tokens;

  const toggleRunner = (runner: string) => {
    setExpandedRunners((current) => {
      const next = new Set(current);
      if (next.has(runner)) {
        next.delete(runner);
      } else {
        next.add(runner);
      }
      return next;
    });
  };

  return (
    <Popover width={620} position="bottom-end" withArrow shadow="md">
      <Popover.Target>
        <Button
          variant="light"
          size="xs"
          leftSection={<IconGauge size={16} />}
          loading={usageSummary.isFetching && !usageSummary.data}
        >
          In {formatTokens(usage.totals.input_tokens)} / Out{' '}
          {formatTokens(usage.totals.output_tokens)} |{' '}
          {formatCost(usage.totals.estimated_cost_usd)}
        </Button>
      </Popover.Target>

      <Popover.Dropdown>
        <Stack gap="sm">
          <Group justify="space-between" align="flex-start">
            <Group gap="sm" align="flex-start" wrap="nowrap">
              <TokenMeterIcon size="lg" />
              <Stack gap={2}>
                <Text fw={700}>Token-o-meter</Text>
                <Text size="xs" c="dimmed">
                  Totals from recorded run history, including archived runs and demo runs.
                </Text>
              </Stack>
            </Group>
            <Badge
              variant="light"
              leftSection={<IconGauge size={14} />}
            >
              {formatTokens(totalTokens)} tokens
            </Badge>
          </Group>

          <Group gap="lg">
            <Stack gap={0}>
              <Text size="xs" c="dimmed">
                Input
              </Text>
              <Text fw={700}>{numberFormatter.format(usage.totals.input_tokens)}</Text>
            </Stack>
            <Stack gap={0}>
              <Text size="xs" c="dimmed">
                Output
              </Text>
              <Text fw={700}>{numberFormatter.format(usage.totals.output_tokens)}</Text>
            </Stack>
            <Stack gap={0}>
              <Text size="xs" c="dimmed">
                Estimated spend
              </Text>
              <Text fw={700}>{formatCost(usage.totals.estimated_cost_usd)}</Text>
            </Stack>
            <Stack gap={0}>
              <Text size="xs" c="dimmed">
                Runs
              </Text>
              <Text fw={700}>
                {usage.totals.runs}
                {usage.totals.demo_runs > 0 ? ` (${usage.totals.demo_runs} demo)` : ''}
              </Text>
            </Stack>
          </Group>

          {usage.by_model.length === 0 ? (
            <Text size="sm" c="dimmed">
              No token usage has been recorded yet.
            </Text>
          ) : (
            <ScrollArea.Autosize mah="60vh" offsetScrollbars>
              <Stack gap={4}>
                <Text size="sm" fw={700}>
                  By model
                </Text>
                <Table fz="xs" striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Model</Table.Th>
                      <Table.Th>Runs</Table.Th>
                      <Table.Th>Input</Table.Th>
                      <Table.Th>Output</Table.Th>
                      <Table.Th>Total</Table.Th>
                      <Table.Th>Cost</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {usage.by_model.map((model) => {
                      const modelTokenTotal = model.input_tokens + model.output_tokens;

                      return (
                        <Table.Tr key={model.model}>
                          <Table.Td>
                            <Stack gap={0}>
                              <Text size="xs" fw={600}>
                                {model.model}
                              </Text>
                              {model.demo_runs > 0 ? (
                                <Text size="xs" c="dimmed">
                                  {model.demo_runs} demo run{model.demo_runs === 1 ? '' : 's'}
                                </Text>
                              ) : null}
                            </Stack>
                          </Table.Td>
                          <Table.Td>{model.runs}</Table.Td>
                          <Table.Td>{numberFormatter.format(model.input_tokens)}</Table.Td>
                          <Table.Td>{numberFormatter.format(model.output_tokens)}</Table.Td>
                          <Table.Td>{numberFormatter.format(modelTokenTotal)}</Table.Td>
                          <Table.Td>{formatCost(model.estimated_cost_usd)}</Table.Td>
                        </Table.Tr>
                      );
                    })}
                  </Table.Tbody>
                </Table>
              </Stack>

              <Stack gap={4} mt="sm">
                <Text size="sm" fw={700}>
                  By runner
                </Text>
                <Table fz="xs" striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th aria-label="Expand runner" />
                      <Table.Th>Runner</Table.Th>
                      <Table.Th>Runs</Table.Th>
                      <Table.Th>Input</Table.Th>
                      <Table.Th>Output</Table.Th>
                      <Table.Th>Total</Table.Th>
                      <Table.Th>Cost</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {usage.by_runner.map((runner) => {
                      const expanded = expandedRunners.has(runner.runner);
                      const hasModels = runner.models.length > 0;

                      return (
                        <>
                          <Table.Tr key={runner.runner}>
                            <Table.Td w={34}>
                              <ActionIcon
                                variant="subtle"
                                size="xs"
                                disabled={!hasModels}
                                aria-label={
                                  expanded
                                    ? `Collapse ${runner.runner} model details`
                                    : `Expand ${runner.runner} model details`
                                }
                                onClick={() => toggleRunner(runner.runner)}
                              >
                                <IconChevronRight
                                  size={14}
                                  style={{
                                    transform: expanded ? 'rotate(90deg)' : undefined,
                                    transition: 'transform 120ms ease',
                                  }}
                                />
                              </ActionIcon>
                            </Table.Td>
                            <Table.Td>
                              <Stack gap={0}>
                                <Text size="xs" fw={600}>
                                  {runner.runner}
                                </Text>
                                {runner.demo_runs > 0 ? (
                                  <Text size="xs" c="dimmed">
                                    {runner.demo_runs} demo run
                                    {runner.demo_runs === 1 ? '' : 's'}
                                  </Text>
                                ) : null}
                              </Stack>
                            </Table.Td>
                            <TokenUsageCells usage={runner} />
                          </Table.Tr>
                          <Table.Tr key={`${runner.runner}-models`}>
                            <Table.Td colSpan={7} p={0}>
                              <Collapse in={expanded}>
                                <Table fz="xs" withRowBorders={false}>
                                  <Table.Thead>
                                    <Table.Tr>
                                      <Table.Th pl={44}>Model</Table.Th>
                                      <Table.Th>Runs</Table.Th>
                                      <Table.Th>Input</Table.Th>
                                      <Table.Th>Output</Table.Th>
                                      <Table.Th>Total</Table.Th>
                                      <Table.Th>Cost</Table.Th>
                                    </Table.Tr>
                                  </Table.Thead>
                                  <Table.Tbody>
                                    {runner.models.map((model) => (
                                      <Table.Tr key={`${runner.runner}-${model.model}`}>
                                        <Table.Td pl={44}>
                                          <Stack gap={0}>
                                            <Text size="xs">{model.model}</Text>
                                            {model.demo_runs > 0 ? (
                                              <Text size="xs" c="dimmed">
                                                {model.demo_runs} demo run
                                                {model.demo_runs === 1 ? '' : 's'}
                                              </Text>
                                            ) : null}
                                          </Stack>
                                        </Table.Td>
                                        <TokenUsageCells usage={model} />
                                      </Table.Tr>
                                    ))}
                                  </Table.Tbody>
                                </Table>
                              </Collapse>
                            </Table.Td>
                          </Table.Tr>
                        </>
                      );
                    })}
                  </Table.Tbody>
                </Table>
              </Stack>
            </ScrollArea.Autosize>
          )}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}
