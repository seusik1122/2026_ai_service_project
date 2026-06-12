import {
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";

interface SentimentGaugeProps {
  /** 긍정 비율 0~1 */
  ratio: number;
}

function gaugeColor(ratio: number): string {
  if (ratio >= 0.66) return "#22c55e";
  if (ratio >= 0.33) return "#fbbf24";
  return "#ef4444";
}

export default function SentimentGauge({ ratio }: SentimentGaugeProps) {
  const percent = Math.round(Math.min(Math.max(ratio, 0), 1) * 100);
  const data = [{ name: "positive", value: percent }];

  return (
    <div className="relative flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          data={data}
          startAngle={210}
          endAngle={-30}
          innerRadius="70%"
          outerRadius="100%"
        >
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar background dataKey="value" cornerRadius={8} fill={gaugeColor(ratio)} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-2xl font-bold">{percent}%</span>
        <span className="text-xs text-gray-400">긍정</span>
      </div>
    </div>
  );
}
