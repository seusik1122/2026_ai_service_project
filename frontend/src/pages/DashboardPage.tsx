import { useMemo } from "react";
import { Link } from "react-router-dom";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { useLectures } from "../hooks/useLectures";
import TrustTrendChart, { TrustTrendPoint } from "../components/charts/TrustTrendChart";
import PlatformCompareChart, { PlatformDatum } from "../components/charts/PlatformCompareChart";
import CategoryPieChart, { CategoryDatum } from "../components/charts/CategoryPieChart";
import SentimentGauge from "../components/charts/SentimentGauge";
import { Lecture } from "../types/lecture";

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
}

function ChartCard({ title, children }: ChartCardProps) {
  return (
    <div className="border rounded-lg p-4 h-64 flex flex-col">
      <h3 className="font-semibold text-sm mb-2">{title}</h3>
      {children}
    </div>
  );
}

function avg(nums: number[]): number {
  if (nums.length === 0) return 0;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function buildPlatformData(lectures: Lecture[]): PlatformDatum[] {
  const groups = new Map<string, Lecture[]>();
  for (const l of lectures) {
    const arr = groups.get(l.platform) ?? [];
    arr.push(l);
    groups.set(l.platform, arr);
  }
  return Array.from(groups.entries()).map(([platform, items]) => ({
    platform,
    count: items.length,
    avgTrust: Math.round(avg(items.map((i) => i.trust_score ?? 0))),
  }));
}

function buildCategoryData(lectures: Lecture[]): CategoryDatum[] {
  const groups = new Map<string, number>();
  for (const l of lectures) {
    const key = l.category ?? "기타";
    groups.set(key, (groups.get(key) ?? 0) + 1);
  }
  return Array.from(groups.entries()).map(([category, count]) => ({ category, count }));
}

// 신뢰도 추이: 전용 시계열 API 연동 전까지 플랫폼별 평균 신뢰도를 추이로 표시 (파생값)
function buildTrustTrend(platformData: PlatformDatum[]): TrustTrendPoint[] {
  return platformData.map((p) => ({ label: p.platform, score: p.avgTrust }));
}

export default function DashboardPage() {
  const { data, isLoading } = useLectures({ limit: 100 });
  const lectures = useMemo(() => data?.lectures ?? [], [data]);

  const platformData = useMemo(() => buildPlatformData(lectures), [lectures]);
  const categoryData = useMemo(() => buildCategoryData(lectures), [lectures]);
  const trendData = useMemo(() => buildTrustTrend(platformData), [platformData]);

  // 감성 분석 게이지: 전용 집계 API 연동 전까지 신뢰도 60점 이상 비율을 긍정 비율로 표시 (파생값)
  const positiveRatio = useMemo(() => {
    if (lectures.length === 0) return 0;
    const positive = lectures.filter((l) => (l.trust_score ?? 0) >= 60).length;
    return positive / lectures.length;
  }, [lectures]);

  const total = data?.total ?? 0;
  const freeCount = lectures.filter((l) => l.is_free).length;
  const platformCount = platformData.length;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">대시보드</h1>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          ← 홈
        </Link>
      </header>

      {isLoading ? (
        <LoadingSpinner />
      ) : (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="border rounded-lg p-4">
            <p className="text-gray-500 text-xs">전체 강의</p>
            <p className="text-2xl font-bold">{total}</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-gray-500 text-xs">무료 강의</p>
            <p className="text-2xl font-bold">{freeCount}</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-gray-500 text-xs">플랫폼 수</p>
            <p className="text-2xl font-bold">{platformCount}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="신뢰도 추이">
          <TrustTrendChart data={trendData} />
        </ChartCard>
        <ChartCard title="플랫폼 비교">
          <PlatformCompareChart data={platformData} />
        </ChartCard>
        <ChartCard title="카테고리 분포">
          <CategoryPieChart data={categoryData} />
        </ChartCard>
        <ChartCard title="감성 분석">
          <SentimentGauge ratio={positiveRatio} />
        </ChartCard>
      </div>
    </div>
  );
}
