import {
  ActionIcon,
  Box,
  Divider,
  Group,
  Stack,
  Text,
  Title,
  Tooltip,
} from '@mantine/core';
import { IconFlask2, IconMail } from '@tabler/icons-react';
import { Link } from 'react-router';
import { AbstractionLevelsModal } from './AbstractionLevelsModal';
import { BrandSignal } from './BrandSignal';
import { DbStatusBadge } from './DbStatusBadge';
import { DemoDataControls } from './DemoDataControls';
import { PricingModal } from './PricingModal';
import { TokenMeterPopover } from './TokenMeterPopover';

const APP_TITLE = 'Just enough AI';
const APP_SUBTITLE = 'Evaluation playground';
const CONTACT_EMAIL = 'danko.mihalic@gmail.com';

export function Navbar() {
  return (
    <Group h="100%" px="md" justify="space-between" align="center" wrap="wrap">
      <Link
        to="/run"
        style={{
          textDecoration: 'none',
          color: 'inherit',
        }}
      >
        <Group gap="xs" wrap="nowrap" className="brand">
          <Box className="brandIcon">
            <IconFlask2 size={32} stroke={1.8} />
          </Box>

          <Stack gap={0}>
            <Title order={5}>{APP_TITLE}</Title>
            <Text size="xs" c="dimmed">
              {APP_SUBTITLE}
            </Text>
            <BrandSignal />
          </Stack>
        </Group>
      </Link>

      <Group gap="xs" wrap="nowrap">
        <Tooltip label="Contact me" multiline maw={320} withArrow openDelay={200}>
          <ActionIcon
            radius="md"
            variant="subtle"
            component="a"
            href={`mailto:${CONTACT_EMAIL}`}
            title="Contact me"
            aria-label="Contact me"
          >
            <IconMail size={18} />
          </ActionIcon>
        </Tooltip>

        <Divider orientation="vertical" />

        <DbStatusBadge />

        <Divider orientation="vertical" />

        <AbstractionLevelsModal />
        <PricingModal />
        <DemoDataControls />
        <TokenMeterPopover />
      </Group>
    </Group>
  );
}
