import { Group, Select, Text, Tooltip } from '@mantine/core';
import { IconBrain, IconLock } from '@tabler/icons-react';
import { useMemo } from 'react';
import { usePricing } from '../hooks/usePricing';
import { HelpIcon } from './HelpIcon';

interface Props {
  value: string | null;
  onChange: (value: string | null) => void;
  disabled?: boolean;
}

export function OpenRouterModelSelect({ value, onChange, disabled }: Props) {
  const pricing = usePricing();
  const { data, disabledReasons, active, defaultActive } = useMemo(() => {
    const models = (pricing.data?.models ?? []).filter((model) =>
      ['OpenRouter', 'OpenAI'].includes(model.provider)
    );
    return {
      data: models.map((model) => ({
        value: model.model,
        label: `${model.provider}: ${model.display_name || model.model}${model.is_free ? ' - free' : ''}`,
        disabled: !model.selectable,
      })),
      disabledReasons: new Map(
        models
          .filter((model) => !model.selectable)
          .map((model) => [model.model, model.notes || `${model.provider} is not configured.`])
      ),
      active: models.find((model) => model.active && model.selectable),
      defaultActive: models.find((model) => model.active),
    };
  }, [pricing.data]);

  return (
    <Select
      label={
        <Group gap={4}>
          LLM model
          <HelpIcon label="Used only by LLM-backed runners. OpenRouter stays available by default; direct OpenAI models appear when JEAI_OPENAI_API_KEY is configured." />
        </Group>
      }
      placeholder={active?.model ?? defaultActive?.model ?? 'Choose a model'}
      data={data}
      value={value ?? active?.model ?? null}
      onChange={onChange}
      leftSection={<IconBrain size={16} />}
      renderOption={({ option }) => {
        const disabledReason = disabledReasons.get(option.value);
        const content = (
          <Group justify="space-between" wrap="nowrap" gap="xs" w="100%">
            <Text size="sm" truncate>
              {option.label}
            </Text>
            {disabledReason ? <IconLock size={14} /> : null}
          </Group>
        );

        return disabledReason ? (
          <Tooltip label={disabledReason} multiline maw={340} withArrow openDelay={200}>
            <div>{content}</div>
          </Tooltip>
        ) : (
          content
        );
      }}
      searchable
      disabled={disabled || pricing.isLoading || data.length === 0}
    />
  );
}
