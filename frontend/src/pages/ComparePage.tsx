import { useState } from "react";
import { Link } from "react-router-dom";
import SearchBar from "../components/common/SearchBar";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { useLectures } from "../hooks/useLectures";
import { formatPrice } from "../utils/formatters";

type SortKey = "trust_score" | "price" | "rating" | "student_count";

const SORT_OPTIONS: { label: string; value: SortKey }[] = [
  { label: "신뢰도순", value: "trust_score" },
  { label: "가격순", value: "price" },
  { label: "평점순", value: "rating" },
  { label: "수강생순", value: "student_count" },
];

export default function ComparePage() {
  const [keyword, setKeyword] = useState("");
  const [sort, setSort] = useState<SortKey>("trust_score");

  const { data, isLoading, isError } = useLectures({
    keyword: keyword || undefined,
    sort,
    limit: 50,
  });

  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">강의 비교</h1>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          ← 홈
        </Link>
      </header>

      <div className="mb-4">
        <SearchBar value={keyword} onChange={setKeyword} placeholder="비교할 강의 검색" />
      </div>

      <div className="flex gap-2 mb-6">
        {SORT_OPTIONS.map((o) => (
          <button
            key={o.value}
            onClick={() => setSort(o.value)}
            className={`px-3 py-1 rounded-full text-sm border ${
              sort === o.value
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-600 border-gray-300"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {isLoading && <LoadingSpinner />}
      {isError && (
        <p className="text-red-500 text-sm py-8 text-center">강의를 불러오지 못했습니다.</p>
      )}
      {data &&
        (data.lectures.length > 0 ? (
          <div className="overflow-x-auto border rounded-lg">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs">
                <tr>
                  <th className="text-left font-medium px-4 py-3">강의</th>
                  <th className="text-left font-medium px-4 py-3">플랫폼</th>
                  <th className="text-right font-medium px-4 py-3">가격</th>
                  <th className="text-right font-medium px-4 py-3">평점</th>
                  <th className="text-right font-medium px-4 py-3">수강생</th>
                  <th className="text-right font-medium px-4 py-3">신뢰도</th>
                </tr>
              </thead>
              <tbody>
                {data.lectures.map((l) => (
                  <tr key={l.id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <p className="font-medium line-clamp-1">{l.title}</p>
                      {l.instructor_name && (
                        <Link
                          to={`/instructor/${encodeURIComponent(l.instructor_name)}`}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          {l.instructor_name}
                        </Link>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{l.platform}</td>
                    <td className="px-4 py-3 text-right">{formatPrice(l.price)}</td>
                    <td className="px-4 py-3 text-right">
                      {l.rating !== undefined ? l.rating.toFixed(1) : "-"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {l.student_count?.toLocaleString() ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {l.trust_score !== undefined ? l.trust_score.toFixed(0) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-400 text-sm py-8 text-center">
            {keyword ? "검색 결과가 없습니다." : "키워드를 입력해 강의를 비교하세요."}
          </p>
        ))}
    </div>
  );
}
