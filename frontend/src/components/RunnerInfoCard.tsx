import { Badge, Card, Group, Text } from '@mantine/core';
import { runnerLevelMeta } from '../lib/runnerLevels';
import type { RunnerInfo } from '../api/types';

interface Props {
  runner?: RunnerInfo;
}

export function RunnerInfoCard({ runner }: Props) {
  if (!runner) return null;

  const meta = runnerLevelMeta(runner.level);
  const Icon = meta.icon;

  return (
    <Card withBorder padding="sm" radius="md">
      <Group gap="xs" wrap="nowrap" align="flex-start">
        <Icon size={18} stroke={1.5} />
        <div style={{ flex: 1 }}>
          <Group gap="xs">
            <Badge color={meta.color} variant="light">
              L{runner.level} · {meta.label}
            </Badge>
          </Group>
          <Text size="sm" c="dimmed" mt={4}>
            {runner.description}
          </Text>
        </div>
      </Group>
    </Card>
  );
}
