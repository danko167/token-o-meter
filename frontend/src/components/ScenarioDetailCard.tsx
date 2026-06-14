import { Badge, Card, Code, Group, Skeleton, Stack, Text } from '@mantine/core';
import type { Scenario, ScenarioFamily } from '../api/types';

interface Props {
  scenario?: Scenario;
  isLoading: boolean;
}

const FAMILY_LABELS: Partial<Record<ScenarioFamily, string>> = {
  customer_support: 'Customer Support',
  policy_qa: 'Policy QA',
  git_diff_review: 'Git Diff Review',
  incident_triage: 'Incident Triage',
  hiring_screening: 'Hiring Screening',
};

export function ScenarioDetailCard({ scenario, isLoading }: Props) {
  if (isLoading) {
    return (
      <Card withBorder padding="md" radius="md">
        <Skeleton height={14} width="50%" mb="sm" />
        <Skeleton height={60} />
      </Card>
    );
  }

  if (!scenario) {
    return (
      <Card withBorder padding="md" radius="md">
        <Text size="sm" c="dimmed">
          Select a scenario to see its input and expectations.
        </Text>
      </Card>
    );
  }

  return (
    <Card withBorder padding="md" radius="md">
      <Stack gap="xs">
        {FAMILY_LABELS[scenario.family] && (
          <Group gap="xs">
            <Badge variant="light" color="violet">
              {FAMILY_LABELS[scenario.family]}
            </Badge>
          </Group>
        )}
        {scenario.description && (
          <Text size="sm" c="dimmed">
            {scenario.description}
          </Text>
        )}
        <Code block>{scenario.input}</Code>
        {Object.keys(scenario.expected).length > 0 && (
          <Group gap="xs">
            <Text size="sm" fw={500}>
              Expected:
            </Text>
            {Object.entries(scenario.expected).map(([key, value]) => (
              <Badge key={key} variant="light" color="blue">
                {key}: {String(value)}
              </Badge>
            ))}
          </Group>
        )}
        {scenario.required_fields.length > 0 && (
          <Group gap="xs">
            <Text size="sm" fw={500}>
              Required fields:
            </Text>
            {scenario.required_fields.map((field) => (
              <Badge key={field} variant="light" color="teal">
                {field}
              </Badge>
            ))}
          </Group>
        )}
        {scenario.forbidden_actions.length > 0 && (
          <Group gap="xs">
            <Text size="sm" fw={500}>
              Forbidden actions:
            </Text>
            {scenario.forbidden_actions.map((action) => (
              <Badge key={action} variant="light" color="red">
                {action}
              </Badge>
            ))}
          </Group>
        )}
      </Stack>
    </Card>
  );
}
