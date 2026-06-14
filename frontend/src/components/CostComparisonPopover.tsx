import { Button, Loader, Popover, ScrollArea, Table, Text } from '@mantine/core';
import { usePricing } from '../hooks/usePricing';

interface Props {
  promptTokens: number;
  completionTokens: number;
}

export function CostComparisonPopover({ promptTokens, completionTokens }: Props) {
  const pricing = usePricing();
  const appModels = (pricing.data?.models ?? []).filter((model) =>
    ['OpenRouter', 'OpenAI'].includes(model.provider)
  );

  if (pricing.isLoading) {
    return <Loader size="xs" />;
  }

  if (appModels.length === 0) {
    return null;
  }

  return (
    <span onClick={(event) => event.stopPropagation()}>
      <Popover width={420} position="bottom-start" withArrow shadow="md">
        <Popover.Target>
          <Button variant="subtle" size="compact-xs">
            View
          </Button>
        </Popover.Target>
        <Popover.Dropdown>
          <Text size="xs" c="dimmed" mb="xs">
            What this run's {promptTokens + completionTokens} tokens would cost on the models
            available in this app.
          </Text>
          <ScrollArea.Autosize mah="35vh" offsetScrollbars>
            <Table fz="xs">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Model</Table.Th>
                  <Table.Th>Est. cost</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {appModels.map((model) => {
                  const inputCost = model.input_cost_per_million_tokens_usd ?? 0;
                  const outputCost = model.output_cost_per_million_tokens_usd ?? 0;
                  const cost =
                    (promptTokens / 1_000_000) * inputCost +
                    (completionTokens / 1_000_000) * outputCost;
                  return (
                    <Table.Tr key={`${model.provider}-${model.model}`}>
                      <Table.Td>
                        {model.provider} {model.display_name}
                      </Table.Td>
                      <Table.Td>${cost.toFixed(6)}</Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </ScrollArea.Autosize>
        </Popover.Dropdown>
      </Popover>
    </span>
  );
}
