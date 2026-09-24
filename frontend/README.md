# Frontend

React + TypeScript + Vite. Recharts for charts. No UI framework, no design
system — the brief asked for a simple, readable dashboard.

```bash
npm install
npm run dev      # http://localhost:5173, /api proxied to localhost:8000
npm run build
npm run lint     # tsc --noEmit
```

Point the dev proxy elsewhere with `VITE_API_TARGET`, or call an absolute API
origin with `VITE_API_BASE`. In production nginx serves the build and proxies
`/api` to the backend on the same origin, so the browser needs no CORS
exception.

## Layout

```
src/
├── App.tsx                 layout and filter state
├── types/index.ts          API contracts mirrored from the backend schemas
├── services/api.ts         fetch wrapper; surfaces the API's structured errors
├── hooks/useDashboard.ts   data loading with cancellation on filter change
└── components/
    ├── FilterBar.tsx       iteration, dates, user, type, memo, capability
    ├── KpiCards.tsx        hours · work items · users · worklog entries
    ├── CapabilityAnalysis.tsx  horizontal bars; click to filter
    ├── TimeCharts.tsx      hours over time, hours by work type
    ├── TopWorkItems.tsx    table; click an id to inspect
    ├── ChatPanel.tsx       conversational panel with expandable evidence
    └── WorkItemDrawer.tsx  metadata, capabilities, worklogs
```

## Two details worth knowing

- **Evidence is always available.** Every agent answer that cites work items
  renders them in a collapsible list, with the filters that were applied, and
  each id opens the work-item drawer. A number the user cannot trace is a number
  they should not trust.
- **Capability overlap is stated in the UI**, not hidden: a work item in two
  capabilities counts in both, so the bars do not sum to the KPI total.
