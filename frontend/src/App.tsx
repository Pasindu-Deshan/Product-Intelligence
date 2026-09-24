import { useState } from 'react';
import { CapabilityAnalysis } from './components/CapabilityAnalysis';
import { ChatPanel } from './components/ChatPanel';
import { FilterBar } from './components/FilterBar';
import { KpiCards } from './components/KpiCards';
import { HoursByMemo, HoursOverTime } from './components/TimeCharts';
import { TopWorkItems } from './components/TopWorkItems';
import { WorkItemDrawer } from './components/WorkItemDrawer';
import { useDashboard, useFilterOptions } from './hooks/useDashboard';
import type { Filters } from './types';
import './styles.css';

export default function App() {
  const [filters, setFilters] = useState<Filters>({});
  const [selectedWorkItem, setSelectedWorkItem] = useState<number | null>(null);
  const { options } = useFilterOptions();
  const { data, loading, error } = useDashboard(filters);

  return (
    <div className="app">
      <header className="app-header">
        <h1>Product Intelligence</h1>
        <p className="muted">Effort analysis over Azure DevOps time logs</p>
      </header>

      <FilterBar options={options} filters={filters} onChange={setFilters} />

      {error && <p className="error">{error}</p>}

      <KpiCards
        totalHours={data?.total_hours ?? 0}
        workItems={data?.work_item_count ?? 0}
        users={data?.user_count ?? 0}
        worklogs={data?.worklog_count ?? 0}
        loading={loading}
      />

      <div className="grid">
        <CapabilityAnalysis
          rows={data?.hours_by_capability ?? []}
          onSelect={(capability) => setFilters({ ...filters, capability })}
        />
        <HoursByMemo rows={data?.hours_by_memo ?? []} />
      </div>

      <HoursOverTime rows={data?.hours_by_date ?? []} />

      <TopWorkItems rows={data?.top_work_items ?? []} onSelect={setSelectedWorkItem} />

      <ChatPanel onInspectWorkItem={setSelectedWorkItem} />

      <WorkItemDrawer workItemId={selectedWorkItem} onClose={() => setSelectedWorkItem(null)} />
    </div>
  );
}
