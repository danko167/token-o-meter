import { useState } from 'react';
import {
  ActionIcon,
  Button,
  Checkbox,
  Group,
  Modal,
  Pagination,
  ScrollArea,
  Select,
  Stack,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { IconArchive, IconArchiveOff, IconRefresh, IconTrash } from '@tabler/icons-react';
import {
  useBulkArchiveRuns,
  useBulkDeleteRuns,
  useBulkUnarchiveRuns,
  useRunsPage,
} from '../hooks/useRuns';
import { RunHistoryTable } from '../components/RunHistoryTable';
import { RunResultPanel } from '../components/RunResultPanel';
import type { RunResult } from '../api/types';

export function HistoryPage() {
  const [showArchived, setShowArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const runs = useRunsPage(showArchived, page, pageSize);
  const [selected, setSelected] = useState<RunResult | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const bulkArchive = useBulkArchiveRuns();
  const bulkUnarchive = useBulkUnarchiveRuns();
  const bulkDelete = useBulkDeleteRuns();

  const visibleRuns = runs.data?.items ?? [];
  const totalRuns = runs.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalRuns / pageSize));

  const toggleRow = (runId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) {
        next.delete(runId);
      } else {
        next.add(runId);
      }
      return next;
    });
  };

  const toggleAll = () => {
    setSelectedIds((prev) => {
      const allSelected = visibleRuns.every((run) => prev.has(run.run_id));
      if (allSelected) {
        return new Set();
      }
      return new Set(visibleRuns.map((run) => run.run_id));
    });
  };

  const handlePageChange = (nextPage: number) => {
    setPage(nextPage);
    setSelectedIds(new Set());
  };

  const handlePageSizeChange = (value: string | null) => {
    setPageSize(Number(value ?? 25));
    setPage(1);
    setSelectedIds(new Set());
  };

  const handleArchive = () => {
    bulkArchive.mutate(Array.from(selectedIds), { onSuccess: () => setSelectedIds(new Set()) });
  };

  const handleUnarchive = () => {
    bulkUnarchive.mutate(Array.from(selectedIds), { onSuccess: () => setSelectedIds(new Set()) });
  };

  const handleDelete = () => {
    bulkDelete.mutate(Array.from(selectedIds), {
      onSuccess: () => {
        setSelectedIds(new Set());
        setConfirmDeleteOpen(false);
      },
    });
  };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={4}>Run History</Title>
        <Group gap="sm">
          <Checkbox
            label="Show archived"
            checked={showArchived}
            onChange={(event) => {
              setShowArchived(event.currentTarget.checked);
              setPage(1);
              setSelectedIds(new Set());
            }}
          />
          <Tooltip label="Refresh">
            <ActionIcon variant="subtle" onClick={() => void runs.refetch()} loading={runs.isFetching}>
              <IconRefresh size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
      {selectedIds.size > 0 && (
        <Group gap="sm">
          <Text size="sm" c="dimmed">
            {selectedIds.size} selected
          </Text>
          {showArchived ? (
            <Button
              size="xs"
              variant="light"
              leftSection={<IconArchiveOff size={14} />}
              loading={bulkUnarchive.isPending}
              onClick={handleUnarchive}
            >
              Unarchive selected
            </Button>
          ) : (
            <Button
              size="xs"
              variant="light"
              leftSection={<IconArchive size={14} />}
              loading={bulkArchive.isPending}
              onClick={handleArchive}
            >
              Archive selected
            </Button>
          )}
          <Button
            size="xs"
            color="red"
            variant="subtle"
            leftSection={<IconTrash size={14} />}
            onClick={() => setConfirmDeleteOpen(true)}
          >
            Delete selected
          </Button>
        </Group>
      )}
      <RunHistoryTable
        runs={visibleRuns}
        isLoading={runs.isLoading}
        onSelect={setSelected}
        selectedIds={selectedIds}
        onToggleRow={toggleRow}
        onToggleAll={toggleAll}
      />
      <Group justify="space-between" align="center">
        <Text size="sm" c="dimmed">
          {totalRuns === 0
            ? 'No runs'
            : `Showing ${(page - 1) * pageSize + 1}-${Math.min(page * pageSize, totalRuns)} of ${totalRuns}`}
        </Text>
        <Group gap="sm">
          <Text size="sm">Rows per page:</Text>
          <Select
            size="xs"
            value={String(pageSize)}
            data={['10', '25', '50', '100']}
            allowDeselect={false}
            w={60}
            onChange={handlePageSizeChange}
          />
          <Pagination
            value={page}
            total={totalPages}
            onChange={handlePageChange}
            size="xs"
            withEdges
          />
        </Group>
      </Group>
      <Modal
        opened={selected !== null}
        onClose={() => setSelected(null)}
        title="Run details"
        size="80%"
        scrollAreaComponent={ScrollArea.Autosize}
        styles={{ body: { overflowX: 'hidden' } }}
      >
        {selected && <RunResultPanel key={selected.run_id} result={selected} isPending={false} error={null} />}
      </Modal>
      <Modal
        opened={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        title="Delete selected runs?"
        size="sm"
        scrollAreaComponent={ScrollArea.Autosize}
      >
        <Stack gap="md">
          <Text size="sm">
            This will permanently delete {selectedIds.size} run{selectedIds.size === 1 ? '' : 's'}.
            This cannot be undone.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmDeleteOpen(false)}>
              Cancel
            </Button>
            <Button color="red" loading={bulkDelete.isPending} onClick={handleDelete}>
              Delete
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

export default HistoryPage;
