import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { WorkItemDetail } from '../types';

interface Props {
  workItemId: number | null;
  onClose: () => void;
}

export function WorkItemDrawer({ workItemId, onClose }: Props) {
  const [detail, setDetail] = useState<WorkItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (workItemId === null) return;
    setDetail(null);
    setError(null);
    api.workItem(workItemId).then(setDetail).catch((e) => setError(e.message));
  }, [workItemId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (workItemId === null) return null;

  return (
    <aside className="drawer" role="dialog" aria-label={`Work item ${workItemId}`}>
      <header>
        <strong>#{workItemId}</strong>
        <button type="button" className="link" onClick={onClose}>Close</button>
      </header>

      {error && <p className="error">{error}</p>}
      {!detail && !error && <p className="muted">Loading…</p>}

      {detail && (
        <>
          <h3>{detail.title}</h3>
          <dl className="meta">
            <dt>Type</dt><dd>{detail.work_item_type ?? '—'}</dd>
            <dt>State</dt><dd>{detail.state ?? '—'}</dd>
            <dt>Assigned to</dt><dd>{detail.assigned_to ?? '—'}</dd>
            <dt>Iteration</dt><dd>{detail.iteration_path ?? '—'}</dd>
            <dt>Total hours</dt><dd>{detail.total_hours.toFixed(1)}</dd>
          </dl>

          {detail.capabilities.length > 0 && (
            <>
              <h4>Capabilities</h4>
              <ul className="chips">
                {detail.capabilities.map((c) => (
                  <li key={c.capability} className={c.confidence < 0.6 ? 'chip warn' : 'chip'}>
                    {c.capability}
                    {c.sub_capability ? ` / ${c.sub_capability}` : ''}
                    <span className="muted"> {(c.confidence * 100).toFixed(0)}%</span>
                    {c.is_human_reviewed && <span className="muted"> · reviewed</span>}
                  </li>
                ))}
              </ul>
            </>
          )}

          <h4>Worklogs</h4>
          <table className="table compact">
            <thead>
              <tr><th>Date</th><th>User</th><th>Type</th><th className="right">Hours</th></tr>
            </thead>
            <tbody>
              {detail.worklogs.map((w) => (
                <tr key={w.worklog_id}>
                  <td>{w.work_date}</td>
                  <td>{w.user_id.trim() || <em className="muted">unknown</em>}</td>
                  <td>{w.memo_code}</td>
                  <td className="right">{w.hours.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </aside>
  );
}
