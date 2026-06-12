import { Link, useParams } from "react-router-dom";
import LoadingSpinner from "../components/common/LoadingSpinner";
import Badge from "../components/common/Badge";
import { useInstructor } from "../hooks/useInstructor";
import { Review } from "../types/review";

const SENTIMENT_LABEL: Record<string, string> = {
  positive: "긍정",
  negative: "부정",
  neutral: "중립",
};

const SENTIMENT_COLOR: Record<string, "green" | "red" | "gray"> = {
  positive: "green",
  negative: "red",
  neutral: "gray",
};

interface StatProps {
  label: string;
  value: string;
}

function Stat({ label, value }: StatProps) {
  return (
    <div className="border rounded-lg p-4">
      <p className="text-gray-500 text-xs">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

interface ReviewItemProps {
  review: Review;
}

function ReviewItem({ review }: ReviewItemProps) {
  return (
    <li className="border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400">{review.platform_source}</span>
        {review.sentiment && (
          <Badge
            label={SENTIMENT_LABEL[review.sentiment] ?? review.sentiment}
            color={SENTIMENT_COLOR[review.sentiment] ?? "gray"}
          />
        )}
      </div>
      <p className="text-sm text-gray-700 whitespace-pre-line">{review.content}</p>
      {review.original_url && (
        <a
          href={review.original_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-600 hover:underline mt-2 inline-block"
        >
          원문 보기 →
        </a>
      )}
    </li>
  );
}

export default function InstructorPage() {
  const { name = "" } = useParams<{ name: string }>();
  const { data, isLoading, isError } = useInstructor(name);

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{decodeURIComponent(name)}</h1>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          ← 홈
        </Link>
      </header>

      {isLoading && <LoadingSpinner />}
      {isError && (
        <p className="text-red-500 text-sm py-8 text-center">강사 정보를 불러오지 못했습니다.</p>
      )}

      {data && (
        <>
          <div className="flex items-center gap-2 mb-4">
            {data.platform && <Badge label={data.platform} color="blue" />}
          </div>

          <div className="grid grid-cols-3 gap-4 mb-8">
            <Stat
              label="신뢰도 점수"
              value={data.trust_score !== undefined ? data.trust_score.toFixed(1) : "-"}
            />
            <Stat
              label="긍정 비율"
              value={
                data.positive_ratio !== undefined
                  ? `${(data.positive_ratio * 100).toFixed(0)}%`
                  : "-"
              }
            />
            <Stat label="후기 수" value={String(data.review_count ?? 0)} />
          </div>

          <h2 className="text-lg font-semibold mb-3">최근 후기</h2>
          {data.recent_reviews && data.recent_reviews.length > 0 ? (
            <ul className="space-y-3">
              {data.recent_reviews.map((r) => (
                <ReviewItem key={r.id} review={r} />
              ))}
            </ul>
          ) : (
            <p className="text-gray-400 text-sm py-8 text-center">표시할 후기가 없습니다.</p>
          )}
        </>
      )}
    </div>
  );
}
