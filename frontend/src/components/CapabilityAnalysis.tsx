import type { CapabilityRow } from '../types';

interface Props {
  rows: CapabilityRow[];
  onSelect: (capability: string) => void;
}

export function CapabilityAnalysis({ rows, onSelect }: Props) {
  if (rows.length === 0) {
    return (
      <section className="panel">
        <h2>Capability Analysis</h2>
        <p className="empty">
          No work items in this selection have been classified into a capability yet.
        </p>
      </section>
    );
  }

  const max = Math.max(...rows.map((r) => r.total_hours));
  const anyLowConfidence = rows.some((r) => r.low_confidence_work_items > 0);

  return (
    <section className="panel">
      <h2>Capability Analysis</h2>
      <ul className="bars">
        {rows.map((row) => (
          <li key={`${row.capability}-${row.sub_capability ?? ''}`}>
            <button type="button" className="bar-row" onClick={() => onSelect(row.capability)}>
              <span className="bar-label">{row.capability}</span>
              <span className="bar-track">
                <span className="bar-fill" style={{ width: `${(row.total_hours / max) * 100}%` }} />
              </span>
              <span className="bar-value">
                {row.total_hours.toFixed(1)}h
                {row.low_confidence_work_items > 0 && (
                  <span className="warn" title={`${row.low_confidence_work_items} low-confidence classifications`}>
                    {' '}·{row.low_confidence_work_items} uncertain
                  </span>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="note">
        A work item can belong to more than one capability, so these figures may overlap
        and will not always add up to the total above.
        {anyLowConfidence && ' Items marked uncertain were classified with low confidence.'}
      </p>
    </section>
  );
}
