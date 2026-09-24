import type {
  ChatResponse,
  DashboardSummary,
  FilterOptions,
  Filters,
  WorkItemDetail,
} from '../types';

const BASE = import.meta.env.VITE_API_BASE ?? '/api';

class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly requestId?: string) {
    super(message);
  }
}

function toQuery(filters: Filters, extra: Record<string, string | number> = {}): string {
  const params = new URLSearchParams();
  Object.entries({ ...filters, ...extra }).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== null) {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return query ? `?${query}` : '';
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

  if (!response.ok) {
    // The API returns a structured error; surface its message, never a raw body.
    let message = `Request failed (${response.status})`;
    let requestId: string | undefined;
    try {
      const body = await response.json();
      message = body.error ?? body.detail ?? message;
      requestId = body.request_id;
    } catch {
      /* non-JSON error body: keep the generic message */
    }
    throw new ApiError(message, response.status, requestId);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; llm_configured: boolean }>('/health'),

  filterOptions: () => request<FilterOptions>('/filters'),

  dashboardSummary: (filters: Filters) =>
    request<DashboardSummary>(`/dashboard/summary${toQuery(filters, { top_n: 10 })}`),

  workItem: (id: number) => request<WorkItemDetail>(`/work-items/${id}`),

  chat: (message: string, conversationId: string | null) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),
};

export { ApiError };
