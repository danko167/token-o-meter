import {
  IconCode,
  IconRoute,
  IconSparkles,
  IconTool,
  IconRobot,
  IconUserCheck,
  type Icon,
} from '@tabler/icons-react';
import type { RunResult } from '../api/types';

export interface RunnerLevelMeta {
  label: string;
  color: string;
  icon: Icon;
}

const RUNNER_LEVEL_META: Record<number, RunnerLevelMeta> = {
  0: { label: 'Deterministic Rules', color: 'gray', icon: IconCode },
  1: { label: 'Traditional Automation', color: 'blue', icon: IconRoute },
  2: { label: 'Direct LLM', color: 'violet', icon: IconSparkles },
  3: { label: 'LLM + Tools', color: 'grape', icon: IconTool },
  4: { label: 'Agent Workflow', color: 'orange', icon: IconRobot },
  5: { label: 'Human-in-the-Loop', color: 'red', icon: IconUserCheck },
};

const FALLBACK_META: RunnerLevelMeta = { label: 'Unknown', color: 'gray', icon: IconCode };

export function runnerLevelMeta(level: number): RunnerLevelMeta {
  return RUNNER_LEVEL_META[level] ?? { ...FALLBACK_META, label: `Level ${level}` };
}

export function scoreColor(score: number): string {
  if (score >= 70) return 'green';
  if (score >= 40) return 'yellow';
  return 'red';
}

export function statusColor(status: RunResult['status']): string {
  if (status === 'succeeded') return 'green';
  if (status === 'pending_approval') return 'yellow';
  return 'red';
}
