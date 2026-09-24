import type React from 'react';

import type { FilterOptions, Filters } from '../types';

interface Props {
  options: FilterOptions | null;
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function FilterBar({ options, filters, onChange }: Props) {
  const set = (key: keyof Filters) => (event: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) =>
    onChange({ ...filters, [key]: event.target.value || undefined });

  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <section className="filters" aria-label="Filters">
      <label>
        Iteration
        <select value={filters.iteration_path ?? ''} onChange={set('iteration_path')}>
          <option value="">All</option>
          {options?.iterations.map((i) => (
            <option key={i} value={i}>{i}</option>
          ))}
        </select>
      </label>

      <label>
        From
        <input type="date" value={filters.date_from ?? ''} onChange={set('date_from')} />
      </label>

      <label>
        To
        <input type="date" value={filters.date_to ?? ''} onChange={set('date_to')} />
      </label>

      <label>
        User
        <select value={filters.user_id ?? ''} onChange={set('user_id')}>
          <option value="">All</option>
          {options?.users.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
      </label>

      <label>
        Work item type
        <select value={filters.work_item_type ?? ''} onChange={set('work_item_type')}>
          <option value="">All</option>
          {options?.work_item_types.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </label>

      <label>
        Memo code
        <select value={filters.memo_code ?? ''} onChange={set('memo_code')}>
          <option value="">All</option>
          {options?.memo_codes.map((m) => (
            <option key={m.code} value={m.code}>
              {m.description ?? m.code}{m.is_active ? '' : ' (inactive)'}
            </option>
          ))}
        </select>
      </label>

      <label>
        Capability
        <select value={filters.capability ?? ''} onChange={set('capability')}>
          <option value="">All</option>
          {options?.capabilities.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </label>

      {hasFilters && (
        <button type="button" className="link" onClick={() => onChange({})}>
          Clear all
        </button>
      )}
    </section>
  );
}
