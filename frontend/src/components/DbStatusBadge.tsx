import { Badge, Tooltip, Stack, Text } from '@mantine/core';
import { useDbHealth } from '../hooks/useHealth';

export function DbStatusBadge() {
  const db = useDbHealth();
  const status = db.data?.status ?? 'checking';
  const color = status === 'ok' ? 'green' : status === 'migration_pending' ? 'yellow' : 'gray';

  return (
    <Tooltip
      label={
        db.data ? (
          <Stack gap={0}>
            <Text size="xs">
              DB revision: {db.data.current_revision ?? 'none'}
            </Text>
            <Text size="xs">
              Head: {db.data.head_revision ?? 'none'}
            </Text>
          </Stack>
        ) : (
          'Checking database migration status'
        )
      }
    >
      <Badge size="sm" color={color} variant="light">
        DB {status}
      </Badge>
    </Tooltip>
  );
}
