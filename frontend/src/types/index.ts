export interface Filters {
  iteration_path?: string;
  date_from?: string;
  date_to?: string;
  user_id?: string;
  work_item_type?: string;
  memo_code?: string;
  time_code?: string;
  capability?: string;
}

export interface FilterOptions {
  iterations: string[];
  users: string[];
  work_item_types: string[];
  memo_codes: { code: string; description: string | null; is_active: boolean }[];
  time_codes: { code: string; name: string; is_active: boolean }[];
  capabilities: string[];
}

export interface MemoRow {
  memo_code: string;
  memo_description: string | null;
  total_hours: number;
  worklog_count: number;
  percentage: number;
}

export interface CapabilityRow {
  capability: string;
  sub_capability: string | null;
  total_hours: number;
  work_item_count: number;
  worklog_count: number;
  percentage: number;
  low_confidence_work_items: number;
}

export interface DateRow {
  period_start: string;
  total_hours: number;
  worklog_count: number;
}

export interface WorkItemRow {
  work_item_id: number;
  title: string | null;
  work_item_type: string | null;
  state: string | null;
  total_hours: number;
  worklog_count: number;
}

export interface DashboardSummary {
  total_hours: number;
  work_item_count: number;
  user_count: number;
  worklog_count: number;
  hours_by_capability: CapabilityRow[];
  hours_by_memo: MemoRow[];
  hours_by_date: DateRow[];
  top_work_items: WorkItemRow[];
  filters_applied: Record<string, unknown>;
}

export interface EvidenceItem {
  work_item_id: number;
  title: string | null;
  hours: number | null;
}

export interface Evidence {
  work_item_ids: number[];
  work_items: EvidenceItem[];
  worklog_count: number | null;
  filters_applied: Record<string, unknown>;
  tools_used: string[];
}

export interface ChatResponse {
  answer: string;
  analytics: Record<string, unknown>;
  evidence: Evidence;
  context: Record<string, unknown>;
  conversation_id: string;
  needs_clarification: boolean;
  unsupported: boolean;
}

export interface ChatTurn {
  role: 'user' | 'agent';
  text: string;
  evidence?: Evidence;
  flavour?: 'normal' | 'clarification' | 'unsupported' | 'error';
}

export interface WorkItemDetail {
  work_item_id: number;
  title: string | null;
  description: string | null;
  work_item_type: string | null;
  state: string | null;
  assigned_to: string | null;
  iteration_path: string | null;
  area_path: string | null;
  total_hours: number;
  worklog_count: number;
  capabilities: {
    capability: string;
    sub_capability: string | null;
    confidence: number;
    is_human_reviewed: boolean;
  }[];
  worklogs: {
    worklog_id: string;
    user_id: string;
    memo_code: string;
    time_code_name: string | null;
    hours: number;
    work_date: string;
    comment: string;
  }[];
}
