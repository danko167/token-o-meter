import { useState } from 'react';
import { Button, Group, Loader, Modal, ScrollArea, Stack, Table, Text } from '@mantine/core';
import { IconStairs } from '@tabler/icons-react';
import { useRunners } from '../hooks/useRunners';
import { runnerLevelMeta } from '../lib/runnerLevels';
import { BrandSignal } from './BrandSignal';

export function AbstractionLevelsModal() {
  const [opened, setOpened] = useState(false);
  const runners = useRunners();
  const sorted = [...(runners.data ?? [])].sort((a, b) => a.level - b.level);

  return (
    <>
      <Button
        leftSection={<IconStairs size={16} />}
        size="xs"
        variant="light"
        onClick={() => setOpened(true)}
      >
        Levels
      </Button>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={
          <Stack gap={6}>
            <span>Abstraction Levels</span>
            <BrandSignal className="brandSignal-modal" />
          </Stack>
        }
        size="80%"
        scrollAreaComponent={ScrollArea.Autosize}
      >
        {runners.isLoading && (
          <Group justify="center" py="xl" gap="sm">
            <Loader size="sm" />
            <Text c="dimmed">Loading runners...</Text>
          </Group>
        )}

        {runners.error && (
          <Text c="red" size="sm">
            {runners.error.message}
          </Text>
        )}

        {runners.data && (
          <Stack>
            <Text size="sm" c="dimmed">
              Every scenario can be run through the same six implementation strategies, from
              plain deterministic rules up to a LangGraph agent with a human-in-the-loop
              checkpoint. Higher levels trade simplicity, speed, and cost for flexibility. Run
              Scenario and Compare label each runner with its level below.
            </Text>
            <Table striped highlightOnHover verticalSpacing="sm" layout="fixed">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={220}>Level</Table.Th>
                  <Table.Th w={140}>Runner</Table.Th>
                  <Table.Th>What it does</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {sorted.map((runner) => {
                  const meta = runnerLevelMeta(runner.level);
                  const Icon = meta.icon;
                  return (
                    <Table.Tr key={runner.name}>
                      <Table.Td>
                        <Group gap={6} wrap="nowrap">
                          <Icon size={16} stroke={1.5} color={`var(--mantine-color-${meta.color}-6)`} />
                          <Text size="sm" fw={600} c={meta.color}>
                            L{runner.level} · {meta.label}
                          </Text>
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm" fw={500}>
                          {runner.name}
                        </Text>
                      </Table.Td>
                      <Table.Td>
                        <Text size="sm">{runner.description}</Text>
                      </Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Stack>
        )}
      </Modal>
    </>
  );
}
