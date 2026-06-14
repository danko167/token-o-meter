import { lazy, Suspense } from 'react';
import { AppShell, Group, Loader, ScrollArea, Tabs, Text } from '@mantine/core';
import {
  IconBulb,
  IconColumns3,
  IconHistory,
  IconPlayerPlay,
  IconUserCheck,
} from '@tabler/icons-react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router';
import { Navbar } from './components/Navbar';

const RunPage = lazy(() => import('./pages/RunPage'));
const ComparePage = lazy(() => import('./pages/ComparePage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));
const RecommendationsPage = lazy(() => import('./pages/RecommendationsPage'));
const HumanMetricsPage = lazy(() => import('./pages/HumanMetricsPage'));

const TABS = [
  {
    path: '/run',
    label: 'Run Scenario',
    Icon: IconPlayerPlay,
    color: 'var(--mantine-color-green-6)',
  },
  {
    path: '/compare',
    label: 'Compare Scenarios',
    Icon: IconColumns3,
    color: 'var(--mantine-color-blue-6)',
  },
  {
    path: '/history',
    label: 'History',
    Icon: IconHistory,
    color: 'var(--mantine-color-grape-6)',
  },
  {
    path: '/recommendations',
    label: 'Recommendations',
    Icon: IconBulb,
    color: 'var(--mantine-color-yellow-7)',
  },
  {
    path: '/human-metrics',
    label: 'Human Metrics',
    Icon: IconUserCheck,
    color: 'var(--mantine-color-teal-6)',
  },
] as const;

function PageFallback() {
  return (
    <Group justify="center" py="xl" gap="sm">
      <Loader size="sm" />
      <Text c="dimmed">Loading...</Text>
    </Group>
  );
}

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const activePath = location.pathname === '/' ? '/run' : location.pathname;

  const handleTabChange = (value: string | null) => {
    navigate(value ?? '/run');
  };

  return (
    <AppShell header={{ height: { base: 104, sm: 64 } }} padding="md">
      <AppShell.Header>
        <Navbar />
      </AppShell.Header>

      <AppShell.Main
        style={{
          height: '100dvh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <Tabs value={activePath} onChange={handleTabChange} mb="md" style={{ flexShrink: 0 }}>
          <Tabs.List grow>
            {TABS.map(({ path, label, Icon, color }) => {
              const isActive = activePath === path;

              return (
                <Tabs.Tab
                  key={path}
                  value={path}
                  style={{ fontWeight: isActive ? 'bold' : 'normal' }}
                >
                  <Icon
                    size={isActive ? 20 : 18}
                    color={isActive ? color : undefined}
                    style={tabIconStyle}
                  />{' '}
                  {label}
                </Tabs.Tab>
              );
            })}
          </Tabs.List>
        </Tabs>

        <ScrollArea style={{ flex: 1, minHeight: 0 }} type="auto" offsetScrollbars>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Navigate to="/run" replace />} />
              <Route path="/run" element={<RunPage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/recommendations" element={<RecommendationsPage />} />
              <Route path="/human-metrics" element={<HumanMetricsPage />} />
              <Route path="*" element={<Navigate to="/run" replace />} />
            </Routes>
          </Suspense>
        </ScrollArea>
      </AppShell.Main>
    </AppShell>
  );
}

const tabIconStyle = { verticalAlign: '-4px', marginRight: 6 };

export default App;