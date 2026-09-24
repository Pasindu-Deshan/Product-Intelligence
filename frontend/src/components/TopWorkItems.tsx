import type { WorkItemRow } from '../types';

interface Props {
  rows: WorkItemRow[];
  onSelect: (workItemId: number) => void;
}

export function TopWorkItems({ rows, onSelect }: Props) {
  if (rows.length === 0) {
    return (
      <section className="panel">
        <h2>Top Work Items</h2>
        <p className="empty">No time has been logged for this selection.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <h2>Top Work Items</h2>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Title</th>
            <th scope="col">Type</th>
            <th scope="col" className="right">Hours</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.work_item_id}>
              <td>
                <button type="button" className="link" onClick={() => onSelect(row.work_item_id)}>
                  {row.work_item_id}
                </button>
              </td>
              <td>{row.title ?? <em className="muted">Not yet synced from Azure DevOps</em>}</td>
              <td>{row.work_item_type ?? '—'}</td>
              <td className="right">{row.total_hours.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
