import { useState } from "react";
import { Link } from "react-router-dom";
import SearchBar from "../components/common/SearchBar";
import LoadingSpinner from "../components/common/LoadingSpinner";
import Badge from "../components/common/Badge";
import { useExams } from "../hooks/useExams";
import { Exam } from "../types/exam";
import { formatDday } from "../utils/formatters";

const DDAY_FILTERS = [
  { label: "전체", value: undefined },
  { label: "30일 이내", value: 30 },
  { label: "60일 이내", value: 60 },
  { label: "90일 이내", value: 90 },
] as const;

function ddayColor(dDay?: number): "red" | "blue" | "gray" {
  if (dDay === undefined) return "gray";
  if (dDay <= 7) return "red";
  if (dDay <= 30) return "blue";
  return "gray";
}

interface ExamCardProps {
  exam: Exam;
}

function ExamCard({ exam }: ExamCardProps) {
  return (
    <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-sm">{exam.exam_name}</h3>
        {exam.d_day !== undefined && (
          <Badge label={formatDday(exam.d_day)} color={ddayColor(exam.d_day)} />
        )}
      </div>
      {exam.exam_type && <p className="text-gray-500 text-xs mt-1">{exam.exam_type}</p>}
      <dl className="mt-3 space-y-1 text-xs text-gray-600">
        {exam.application_start && exam.application_end && (
          <div className="flex justify-between">
            <dt className="text-gray-400">접수</dt>
            <dd>
              {exam.application_start} ~ {exam.application_end}
            </dd>
          </div>
        )}
        {exam.exam_date && (
          <div className="flex justify-between">
            <dt className="text-gray-400">시험일</dt>
            <dd>{exam.exam_date}</dd>
          </div>
        )}
        {exam.result_date && (
          <div className="flex justify-between">
            <dt className="text-gray-400">발표</dt>
            <dd>{exam.result_date}</dd>
          </div>
        )}
      </dl>
      {exam.related_keywords && exam.related_keywords.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {exam.related_keywords.map((k) => (
            <span key={k} className="px-2 py-0.5 rounded bg-gray-100 text-gray-600 text-xs">
              {k}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ExamPage() {
  const [keyword, setKeyword] = useState("");
  const [dDayWithin, setDDayWithin] = useState<number | undefined>(undefined);

  const { data, isLoading, isError } = useExams({
    keyword: keyword || undefined,
    d_day_within: dDayWithin,
  });

  return (
    <div className="max-w-4xl mx-auto px-4 py-6">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">자격증 시험 일정</h1>
        <Link to="/" className="text-sm text-blue-600 hover:underline">
          ← 홈
        </Link>
      </header>

      <div className="mb-4">
        <SearchBar value={keyword} onChange={setKeyword} placeholder="시험명 검색" />
      </div>

      <div className="flex gap-2 mb-6">
        {DDAY_FILTERS.map((f) => (
          <button
            key={f.label}
            onClick={() => setDDayWithin(f.value)}
            className={`px-3 py-1 rounded-full text-sm border ${
              dDayWithin === f.value
                ? "bg-blue-600 text-white border-blue-600"
                : "bg-white text-gray-600 border-gray-300"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading && <LoadingSpinner />}
      {isError && (
        <p className="text-red-500 text-sm py-8 text-center">시험 일정을 불러오지 못했습니다.</p>
      )}
      {data && (
        <>
          <p className="text-gray-500 text-sm mb-3">총 {data.exams.length}개</p>
          {data.exams.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {data.exams.map((e) => (
                <ExamCard key={e.id} exam={e} />
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm py-8 text-center">조건에 맞는 시험이 없습니다.</p>
          )}
        </>
      )}
    </div>
  );
}
