import { Link } from "react-router-dom";
import RecommendSection from "../components/lecture/RecommendSection";

export default function HomePage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">강의 통합 추천</h1>
        <Link to="/dashboard" className="text-sm text-blue-600 hover:underline">
          대시보드 →
        </Link>
      </header>

      <RecommendSection />
    </div>
  );
}
