import { Badge, Center, Checkbox, Group, Loader, Table, Text, Tooltip } from '@mantine/core';
import type { RunResult } from '../api/types';
import { statusColor } from '../lib/runnerLevels';

interface Props {
  runs: RunResult[];
  isLoading: boolean;
  onSelect: (run: RunResult) => void;
  selectedIds: Set<string>;
  onToggleRow: (runId: string) => void;
  onToggleAll: () => void;
}

export function RunHistoryTable({
  runs,
  isLoading,
  onSelect,
  selectedIds,
  onToggleRow,
  onToggleAll,
}: Props) {
  if (isLoading) {
    return (
      <Center py="xl">
        <Loader size="sm" />
      </Center>
    );
  }

  if (runs.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="xl">
        No runs yet - execute a scenario from the "Run Scenario" tab.
      </Text>
    );
  }

  const allSelected = runs.every((run) => selectedIds.has(run.run_id));
  const someSelected = runs.some((run) => selectedIds.has(run.run_id));

  return (
    <Table highlightOnHover striped>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>
            <Checkbox
              aria-label="Select all runs"
              checked={allSelected}
              indeterminate={someSelected && !allSelected}
              onChange={onToggleAll}
            />
          </Table.Th>
          <Table.Th>Created</Table.Th>
          <Table.Th>Scenario</Table.Th>
          <Table.Th>Runner</Table.Th>
          <Table.Th>Status</Table.Th>
          <Table.Th>Score</Table.Th>
          <Table.Th>Tokens</Table.Th>
          <Table.Th>Duration</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {runs.map((run) => (
          <Table.Tr key={run.run_id} onClick={() => onSelect(run)} style={{ cursor: 'pointer' }}>
            <Table.Td onClick={(event) => event.stopPropagation()}>
              <Checkbox
                aria-label={`Select run ${run.run_id}`}
                checked={selectedIds.has(run.run_id)}
                onChange={() => onToggleRow(run.run_id)}
              />
            </Table.Td>
            <Table.Td>{new Date(run.created_at).toLocaleString()}</Table.Td>
            <Table.Td>{run.scenario_id}</Table.Td>
            <Table.Td>
              <Group gap="xs">
                <Text size="sm">{run.runner}</Text>
                {run.is_demo && (
                  <Badge size="xs" color="gray" variant="light">
                    demo
                  </Badge>
                )}
                {run.archived && (
                  <Badge size="xs" color="gray" variant="light">
                    archived
                  </Badge>
                )}
              </Group>
            </Table.Td>
            <Table.Td>
              {run.status === 'failed' && run.error ? (
                <Tooltip label={run.error} multiline maw={360} withArrow>
                  <Badge color="red" variant="light">
                    {run.status}
                  </Badge>
                </Tooltip>
              ) : (
                <Badge color={statusColor(run.status)} variant="light">
                  {run.status}
                </Badge>
              )}
            </Table.Td>
            <Table.Td>{run.evaluation ? run.evaluation.score : '—'}</Table.Td>
            <Table.Td>{run.metrics.prompt_tokens + run.metrics.completion_tokens}</Table.Td>
            <Table.Td>{run.metrics.duration_ms} ms</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
