import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export interface PlatformDatum {
  platform: string;
  count: number;
  avgTrust: number;
}

interface PlatformCompareChartProps {
  data: PlatformDatum[];
}

export default function PlatformCompareChart({ data }: PlatformCompareChartProps) {
  if (data.length === 0) {
    return <div className="flex-1 flex items-center justify-center text-gray-300 text-xs">데이터 없음</div>;
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="platform" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="count" name="강의 수" fill="#2563eb" radius={[4, 4, 0, 0]} />
        <Bar dataKey="avgTrust" name="평균 신뢰도" fill="#93c5fd" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
