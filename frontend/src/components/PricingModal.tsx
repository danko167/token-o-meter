import { useState } from 'react';
import { Badge, Button, Group, Loader, Modal, ScrollArea, Stack, Table, Text } from '@mantine/core';
import { IconCurrencyDollar } from '@tabler/icons-react';
import { usePricing } from '../hooks/usePricing';
import { BrandSignal } from './BrandSignal';
import { HelpIcon } from './HelpIcon';

export function PricingModal() {
  const [opened, setOpened] = useState(false);
  const pricing = usePricing();

  return (
    <>
      <Button
        leftSection={<IconCurrencyDollar size={16} />}
        size="xs"
        variant="light"
        onClick={() => setOpened(true)}
      >
        Model prices
      </Button>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={
          <Stack gap={6}>
            <span>Model Pricing</span>
            <BrandSignal className="brandSignal-modal" />
          </Stack>
        }
        size="80%"
        scrollAreaComponent={ScrollArea.Autosize}
      >
        {pricing.isLoading && (
          <Group justify="center" py="xl" gap="sm">
            <Loader size="sm" />
            <Text c="dimmed">Loading pricing...</Text>
          </Group>
        )}

        {pricing.error && (
          <Text c="red" size="sm">
            {pricing.error.message}
          </Text>
        )}

        {pricing.data && (
          <Stack>
            <Group gap={4}>
              <Text size="sm" c="dimmed">
                Costs are shown in {pricing.data.currency}, {pricing.data.unit.replaceAll('_', ' ')}.
              </Text>
              <HelpIcon label="The backend uses these values to estimate run cost from prompt and completion token counts." />
            </Group>
            <Text size="xs" c="dimmed">
              "Selectable" models are routed through OpenRouter and can be picked for a run.
              Check OpenRouter for the most up-to-date availability, pricing, and free-tier
              limits. "Reference" rows show commercial providers' list prices for cost
              comparison only and aren't selectable here.
            </Text>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Provider</Table.Th>
                  <Table.Th>Model</Table.Th>
                  <Table.Th>Input / 1M</Table.Th>
                  <Table.Th>Output / 1M</Table.Th>
                  <Table.Th>Type</Table.Th>
                  <Table.Th>Status</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {pricing.data.models.map((model) => (
                  <Table.Tr key={`${model.provider}-${model.model}`}>
                    <Table.Td>{model.provider}</Table.Td>
                    <Table.Td>
                      <Stack gap={0}>
                        <Text size="sm" fw={500}>{model.display_name || model.model}</Text>
                        <Text size="xs" c="dimmed">{model.model}</Text>
                        {model.notes && <Text size="xs" c="dimmed">{model.notes}</Text>}
                      </Stack>
                    </Table.Td>
                    <Table.Td>{formatUsd(model.input_cost_per_million_tokens_usd)}</Table.Td>
                    <Table.Td>{formatUsd(model.output_cost_per_million_tokens_usd)}</Table.Td>
                    <Table.Td>
                      <Badge color={model.is_free ? 'teal' : 'blue'} variant="light">
                        {model.is_free ? 'free' : 'paid'}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Badge color={model.active ? 'green' : 'gray'} variant="light">
                        {model.active ? 'default' : model.selectable ? 'selectable' : 'reference'}
                      </Badge>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Stack>
        )}
      </Modal>
    </>
  );
}

function formatUsd(value: number | null) {
  if (value === null) {
    return 'not listed';
  }
  if (value === 0) {
    return 'free';
  }
  return `$${value.toFixed(3)}`;
}
