import type React from 'react';

import type { FilterOptions, Filters } from '../types';

interface Props {
  options: FilterOptions | null;
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function FilterBar({ options, filters, onChange }: Props) {
  const set =
    (key: keyof Filters) =>
    (event: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
      const value = event.target.value || undefined;

      onChange({
        ...filters,
        [key]: value,
      });
    };

  const setFromDate = (event: React.ChangeEvent<HTMLInputElement>) => {
    const dateFrom = event.target.value || undefined;

    const updatedFilters: Filters = {
      ...filters,
      date_from: dateFrom,
    };

    // If the new From date is after the current To date,
    // clear the To date because it is no longer valid.
    if (
      dateFrom &&
      filters.date_to &&
      filters.date_to < dateFrom
    ) {
      updatedFilters.date_to = undefined;
    }

    onChange(updatedFilters);
  };

  const setToDate = (event: React.ChangeEvent<HTMLInputElement>) => {
    const dateTo = event.target.value || undefined;

    // Prevent a To date earlier than the From date.
    if (
      dateTo &&
      filters.date_from &&
      dateTo < filters.date_from
    ) {
      return;
    }

    onChange({
      ...filters,
      date_to: dateTo,
    });
  };

  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <section className="filters" aria-label="Filters">
      <label>
        Iteration
        <select
          value={filters.iteration_path ?? ''}
          onChange={set('iteration_path')}
        >
          <option value="">All</option>

          {options?.iterations.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
      </label>

      <label>
        From
        <input
          type="date"
          value={filters.date_from ?? ''}
          onChange={setFromDate}
        />
      </label>

      <label>
        To
        <input
          type="date"
          value={filters.date_to ?? ''}
          min={filters.date_from ?? undefined}
          onChange={setToDate}
        />
      </label>

      <label>
        User
        <select
          value={filters.user_id ?? ''}
          onChange={set('user_id')}
        >
          <option value="">All</option>

          {options?.users.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </label>

      <label>
        Work item type
        <select
          value={filters.work_item_type ?? ''}
          onChange={set('work_item_type')}
        >
          <option value="">All</option>

          {options?.work_item_types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label>
        Memo code
        <select
          value={filters.memo_code ?? ''}
          onChange={set('memo_code')}
        >
          <option value="">All</option>

          {options?.memo_codes.map((m) => (
            <option key={m.code} value={m.code}>
              {m.description ?? m.code}
              {m.is_active ? '' : ' (inactive)'}
            </option>
          ))}
        </select>
      </label>

      <label>
        Capability
        <select
          value={filters.capability ?? ''}
          onChange={set('capability')}
        >
          <option value="">All</option>

          {options?.capabilities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>

      {hasFilters && (
        <button
          type="button"
          className="link"
          onClick={() => onChange({})}
        >
          Clear all
        </button>
      )}
    </section>
  );
}