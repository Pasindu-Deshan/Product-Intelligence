interface Props {
  totalHours: number;
  workItems: number;
  users: number;
  worklogs: number;
  loading: boolean;
}

const format = (value: number) =>
  value.toLocaleString(undefined, { maximumFractionDigits: 1 });

export function KpiCards({ totalHours, workItems, users, worklogs, loading }: Props) {
  const cards = [
    { label: 'Hours', value: format(totalHours) },
    { label: 'Work Items', value: format(workItems) },
    { label: 'Users', value: format(users) },
    { label: 'Worklog Entries', value: format(worklogs) },
  ];

  return (
    <section className="kpis" aria-busy={loading}>
      {cards.map((card) => (
        <div className="kpi" key={card.label}>
          <div className="kpi-value">{loading ? '—' : card.value}</div>
          <div className="kpi-label">{card.label}</div>
        </div>
      ))}
    </section>
  );
}
