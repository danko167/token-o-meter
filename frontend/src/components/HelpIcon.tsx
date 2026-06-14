import { ActionIcon, Tooltip } from '@mantine/core';
import { IconQuestionMark } from '@tabler/icons-react';

interface Props {
  label: string;
}

export function HelpIcon({ label }: Props) {
  return (
    <Tooltip label={label} multiline maw={320} withArrow openDelay={200}>
      <ActionIcon
        aria-label={label}
        color="gray"
        radius="xl"
        size="12px"
        variant="outline"
      >
        <IconQuestionMark size={12} />
      </ActionIcon>
    </Tooltip>
  );
}
