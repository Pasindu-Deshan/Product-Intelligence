import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DateRow, MemoRow } from '../types';

const COLOURS = ['#2f6fed', '#00a37a', '#f2a900', '#d1495b', '#6a4c93', '#8d99ae'];

export function HoursOverTime({ rows }: { rows: DateRow[] }) {
  if (rows.length === 0) return null;
  return (
    <section className="panel">
      <h2>Time Distribution</h2>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="period_start" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} unit="h" />
          <Tooltip formatter={(v: number) => `${v.toFixed(1)}h`} />
          <Line type="monotone" dataKey="total_hours" stroke="#2f6fed" strokeWidth={2} dot={false} name="Hours" />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}

export function HoursByMemo({ rows }: { rows: MemoRow[] }) {
  if (rows.length === 0) return null;
  return (
    <section className="panel">
      <h2>Hours by Work Type</h2>
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie
            data={rows}
            dataKey="total_hours"
            nameKey="memo_description"
            innerRadius={45}
            outerRadius={80}
            paddingAngle={2}
          >
            {rows.map((row, index) => (
              <Cell key={row.memo_code} fill={COLOURS[index % COLOURS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(v: number, n) => [`${v.toFixed(1)}h`, n]} />
          <Legend verticalAlign="bottom" iconSize={8} />
        </PieChart>
      </ResponsiveContainer>
    </section>
  );
}

export function HoursByMemoBars({ rows }: { rows: MemoRow[] }) {
  if (rows.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={rows}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="memo_code" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} unit="h" />
        <Tooltip formatter={(v: number) => `${v.toFixed(1)}h`} />
        <Bar dataKey="total_hours" fill="#2f6fed" name="Hours" />
      </BarChart>
    </ResponsiveContainer>
  );
}
