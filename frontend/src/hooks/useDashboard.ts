import { useCallback, useEffect, useState } from 'react';
import { api } from '../services/api';
import type { DashboardSummary, FilterOptions, Filters } from '../types';

export function useFilterOptions() {
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.filterOptions().then(setOptions).catch((e) => setError(e.message));
  }, []);

  return { options, error };
}

export function useDashboard(filters: Filters) {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify(filters);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .dashboardSummary(filters)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => load(), [load]);

  return { data, loading, error, reload: load };
}
