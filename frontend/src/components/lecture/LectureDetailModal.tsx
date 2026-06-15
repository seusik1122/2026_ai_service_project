import { useEffect } from "react";
import { useLectureDetail, useWhyRecommend } from "../../hooks/useLectureDetail";
import { Lecture } from "../../types/lecture";

interface Props {
  lecture: Lecture;
  question?: string;
  onClose: () => void;
}

const PLATFORM_LABELS: Record<string, string> = {
  inflearn: "인프런", fastcampus: "패스트캠퍼스", class101: "클래스101",
  coloso: "콜로소", youtube: "유튜브", hackers: "해커스", siwonschool: "시원스쿨",
  yanadoo: "야나두", megastudy: "메가스터디", ebsi: "EBSi",
  opentutorials: "생활코딩", codeit: "코드잇", nomadcoder: "노마드코더",
};

export default function LectureDetailModal({ lecture, question = "", onClose }: Props) {
  const { data, isLoading } = useLectureDetail(lecture.id);
  const { mutate: fetchWhy, data: whyData, isPending: whyPending } = useWhyRecommend();

  useEffect(() => {
    fetchWhy({ id: lecture.id, question });
  }, [lecture.id]);

  // ESC 키로 닫기
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const instructor = data?.instructor;
  const reviews = data?.reviews ?? [];
  const trustScore = instructor?.trust_score;

  const displayPrice =
    lecture.price === 0 ? "무료" :
    lecture.price === -1 ? "가격 확인 필요" :
    `${lecture.price.toLocaleString()}원`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl">
        {/* 헤더 */}
        <div className="flex items-start justify-between p-5 border-b">
          <div className="flex-1 pr-4">
            <span className="text-xs text-blue-600 font-medium bg-blue-50 px-2 py-0.5 rounded-full">
              {PLATFORM_LABELS[lecture.platform] ?? lecture.platform}
            </span>
            <h2 className="text-base font-bold mt-2 leading-snug">{lecture.title}</h2>
            {lecture.instructor_name && (
              <p className="text-sm text-gray-500 mt-1">{lecture.instructor_name}</p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none flex-shrink-0">✕</button>
        </div>

        <div className="p-5 space-y-5">
          {/* 가격·평점 */}
          <div className="flex items-center gap-4 text-sm">
            <span className="font-bold text-blue-600 text-lg">{displayPrice}</span>
            {lecture.rating && (
              <span className="text-yellow-500">★ {lecture.rating.toFixed(1)}</span>
            )}
            {lecture.student_count && (
              <span className="text-gray-400">{lecture.student_count.toLocaleString()}명 수강</span>
            )}
          </div>

          {/* AI 추천 이유 */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4">
            <p className="text-xs font-semibold text-blue-700 mb-2">AI 추천 이유</p>
            {whyPending ? (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span className="animate-spin">⟳</span> 분석 중...
              </div>
            ) : (
              <p className="text-sm text-gray-700 leading-relaxed">
                {whyData?.reason ?? "추천 이유를 불러오는 중입니다."}
              </p>
            )}
          </div>

          {/* 강사 신뢰도 */}
          {isLoading ? (
            <p className="text-xs text-gray-400">강사 정보 로딩 중...</p>
          ) : (
            <div>
              <p className="text-xs font-semibold text-gray-600 mb-2">강사 신뢰도</p>
              {instructor ? (
                <>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 bg-gray-100 rounded-full h-2.5 overflow-hidden">
                      <div
                        className={`h-2.5 rounded-full transition-all duration-700 ${
                          (trustScore ?? 0) >= 70 ? "bg-green-500" :
                          (trustScore ?? 0) >= 40 ? "bg-yellow-400" : "bg-red-400"
                        }`}
                        style={{ width: `${Math.min(trustScore ?? 0, 100)}%` }}
                      />
                    </div>
                    <span className={`text-sm font-bold ${
                      (trustScore ?? 0) >= 70 ? "text-green-600" :
                      (trustScore ?? 0) >= 40 ? "text-yellow-600" : "text-red-500"
                    }`}>
                      {trustScore != null ? `${trustScore.toFixed(0)}점` : "정보 없음"}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {instructor.review_count
                      ? `후기 ${instructor.review_count}개 기반${instructor.positive_ratio != null ? ` · 긍정 ${(instructor.positive_ratio * 100).toFixed(0)}%` : ""}`
                      : "아직 수집된 후기가 없습니다"}
                  </p>
                </>
              ) : (
                <p className="text-xs text-gray-400">강사 정보가 없습니다</p>
              )}
            </div>
          )}

          {/* 후기 */}
          <div>
            <p className="text-xs font-semibold text-gray-600 mb-2">수강생 후기</p>
            {reviews.length > 0 ? (
              <div className="space-y-2">
                {reviews.map((r) => (
                  <div key={r.id} className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 leading-relaxed">
                    {r.sentiment === "positive" && <span className="text-green-500 mr-1">👍</span>}
                    {r.sentiment === "negative" && <span className="text-red-400 mr-1">👎</span>}
                    {r.content}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 bg-gray-50 rounded-lg p-3">
                아직 수집된 후기가 없습니다. 후기는 매일 자동 수집됩니다.
              </p>
            )}
          </div>

          {/* 원본 링크 + 알림 버튼 */}
          <div className="flex flex-col gap-2">
            {lecture.url && (
              <a
                href={lecture.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full text-center py-3 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                {PLATFORM_LABELS[lecture.platform] ?? lecture.platform}에서 강의 보기 →
              </a>
            )}
            <div className="flex gap-2">
              <a
                href="/exams"
                className="flex-1 text-center py-2.5 border border-gray-200 rounded-xl text-xs text-gray-600 hover:bg-gray-50 transition-colors"
              >
                📅 관련 시험 일정 보기
              </a>
              <span className="flex-1 text-center py-2.5 border border-gray-200 rounded-xl text-xs text-gray-400">
                📧 D-day 이메일 자동 발송 중
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
