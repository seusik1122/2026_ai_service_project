import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

export interface CategoryDatum {
  category: string;
  count: number;
}

interface CategoryPieChartProps {
  data: CategoryDatum[];
}

const COLORS = ["#2563eb", "#60a5fa", "#93c5fd", "#a78bfa", "#f472b6", "#fbbf24", "#34d399"];

export default function CategoryPieChart({ data }: CategoryPieChartProps) {
  if (data.length === 0) {
    return <div className="flex-1 flex items-center justify-center text-gray-300 text-xs">데이터 없음</div>;
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="category"
          cx="50%"
          cy="50%"
          outerRadius="75%"
          label={{ fontSize: 11 }}
        >
          {data.map((entry, i) => (
            <Cell key={entry.category} fill={COLORS[i % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
