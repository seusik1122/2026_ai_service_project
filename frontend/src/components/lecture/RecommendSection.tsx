import { useState } from "react";
import { useRecommend } from "../../hooks/useRecommend";
import { RoadmapStep, sendRecommendEmail, Roadmap } from "../../api/recommend";
import { Lecture, StepGroup } from "../../types/lecture";
import { formatPrice } from "../../utils/formatters";

const EXAMPLES = [
  "토익 처음 시작하는데 돈이 없어요",
  "파이썬 머신러닝 입문, 5만원 이하",
  "일러스트 독학하고 싶어요",
  "프로그래밍 기초부터 배우고 싶어요",
];

const LEVEL_COLORS: Record<string, string> = {
  "초급": "bg-green-100 text-green-700",
  "중급": "bg-yellow-100 text-yellow-700",
  "고급": "bg-red-100 text-red-700",
};

function RoadmapCard({ steps, goal, level }: { steps: RoadmapStep[]; goal: string; level: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="bg-white rounded-2xl border border-indigo-100 p-5 mb-6 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base font-bold text-gray-800">📋 AI 학습 로드맵</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${LEVEL_COLORS[level] ?? "bg-gray-100 text-gray-600"}`}>
            {level}
          </span>
        </div>
        <button onClick={() => setExpanded(!expanded)} className="text-xs text-blue-500 hover:text-blue-700">
          {expanded ? "접기 ▲" : "펼치기 ▼"}
        </button>
      </div>
      <p className="text-sm text-gray-600 mb-4">🎯 목표: {goal}</p>
      <div className="flex items-start gap-0">
        {steps.map((step, idx) => (
          <div key={step.step} className="flex-1 flex flex-col items-center">
            <div className="flex items-center w-full">
              <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center font-bold">
                {step.step}
              </div>
              {idx < steps.length - 1 && <div className="flex-1 h-0.5 bg-blue-200" />}
            </div>
            <div className="mt-2 text-center px-1">
              <p className="text-xs font-semibold text-gray-700">{step.title}</p>
              {expanded && (
                <>
                  {step.duration && <p className="text-xs text-blue-500 mt-0.5">{step.duration}</p>}
                  <p className="text-xs text-gray-500 mt-1 leading-relaxed">{step.description}</p>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface LectureDetailModalProps {
  lecture: Lecture;
  selected: boolean;
  onToggle: () => void;
  onClose: () => void;
}

function LectureDetailModal({ lecture, selected, onToggle, onClose }: LectureDetailModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-6"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto relative"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="sticky top-0 bg-white rounded-t-2xl px-6 pt-5 pb-4 border-b border-gray-100">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 text-xl leading-none"
          >
            ✕
          </button>
          <div className="pr-6">
            <p className="text-base font-bold text-gray-900 leading-snug mb-1">{lecture.title}</p>
            {lecture.instructor_name && (
              <p className="text-xs text-gray-500">{lecture.instructor_name}</p>
            )}
          </div>

          {/* 기본 정보 배지 */}
          <div className="flex flex-wrap gap-2 mt-3">
            <span className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-full font-medium">{lecture.platform}</span>
            <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${
              lecture.is_free ? "bg-green-100 text-green-700" : "bg-orange-50 text-orange-600"
            }`}>
              {lecture.is_free ? "무료" : formatPrice(lecture.price)}
            </span>
            {lecture.level && (
              <span className="text-xs px-2.5 py-1 bg-purple-50 text-purple-700 rounded-full font-medium">
                {lecture.level}
              </span>
            )}
            {lecture.rating != null && (
              <span className="text-xs px-2.5 py-1 bg-yellow-50 text-yellow-700 rounded-full font-medium">
                ★ {lecture.rating.toFixed(1)}
              </span>
            )}
            {lecture.student_count != null && (
              <span className="text-xs px-2.5 py-1 bg-gray-50 text-gray-500 rounded-full">
                수강생 {lecture.student_count.toLocaleString()}명
              </span>
            )}
            {lecture.fit_score != null && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${
                lecture.fit_score >= 8 ? "bg-blue-100 text-blue-700" :
                lecture.fit_score >= 6 ? "bg-indigo-50 text-indigo-600" : "bg-gray-100 text-gray-500"
              }`}>
                적합도 {lecture.fit_score}/10
              </span>
            )}
          </div>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* 강의 소개 */}
          {lecture.description && (
            <div className="bg-gray-50 rounded-xl p-4">
              <p className="text-xs font-bold text-gray-600 mb-2">📖 강의 소개</p>
              <p className="text-sm text-gray-700 leading-relaxed">{lecture.description}</p>
            </div>
          )}

          {/* 추천 이유 */}
          {lecture.reason && (
            <div className="bg-blue-50 rounded-xl p-4">
              <p className="text-xs font-bold text-blue-700 mb-2">📋 이 단계에서 추천하는 이유</p>
              <p className="text-sm text-gray-700 leading-relaxed">{lecture.reason}</p>
            </div>
          )}

          {/* 핵심 장점 */}
          {lecture.pros && lecture.pros.length > 0 && (
            <div className="bg-green-50 rounded-xl p-4">
              <p className="text-xs font-bold text-green-700 mb-2">✅ 핵심 장점</p>
              <ul className="space-y-1.5">
                {lecture.pros.map((pro, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-green-500 mt-0.5 flex-shrink-0">•</span>
                    {pro}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 같은 단계 강의와의 차별점 */}
          {lecture.diff && (
            <div className="bg-indigo-50 rounded-xl p-4">
              <p className="text-xs font-bold text-indigo-700 mb-2">⚡ 다른 후보 강의와의 차별점</p>
              <p className="text-sm text-gray-700 leading-relaxed">{lecture.diff}</p>
            </div>
          )}

          {/* 커리큘럼 */}
          {lecture.curriculum && (
            <div className="bg-violet-50 rounded-xl p-4">
              <p className="text-xs font-bold text-violet-700 mb-2">📚 커리큘럼</p>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{lecture.curriculum}</p>
            </div>
          )}

          {/* 주의사항 */}
          {lecture.caution && (
            <div className="bg-amber-50 rounded-xl p-4">
              <p className="text-xs font-bold text-amber-700 mb-2">⚠️ 선택 전 참고사항</p>
              <p className="text-sm text-gray-700 leading-relaxed">{lecture.caution}</p>
            </div>
          )}

          {/* 키워드 */}
          {lecture.keywords && lecture.keywords.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-400 mb-2">관련 키워드</p>
              <div className="flex flex-wrap gap-1">
                {lecture.keywords.map((kw) => (
                  <span key={kw} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-500 rounded-full">{kw}</span>
                ))}
              </div>
            </div>
          )}

          {/* 태그 */}
          {lecture.tags && lecture.tags.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-400 mb-2">태그</p>
              <div className="flex flex-wrap gap-1">
                {lecture.tags.map((tag) => (
                  <span key={tag} className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded-full">{tag}</span>
                ))}
              </div>
            </div>
          )}

          {/* 강의 링크 */}
          {lecture.url && (
            <a
              href={lecture.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-1 w-full py-2 border border-blue-200 rounded-xl text-sm text-blue-600 hover:bg-blue-50 transition-colors"
            >
              강의 페이지 바로가기 →
            </a>
          )}
        </div>

        {/* 하단 버튼 */}
        <div className="sticky bottom-0 bg-white border-t border-gray-100 px-6 py-4 flex gap-2 rounded-b-2xl">
          <button
            onClick={() => { onToggle(); onClose(); }}
            className={`flex-1 py-3 rounded-xl text-sm font-bold transition-colors ${
              selected
                ? "bg-gray-100 text-gray-600 hover:bg-gray-200"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {selected ? "✓ 선택 취소" : "이 강의 선택하기"}
          </button>
          <button
            onClick={onClose}
            className="px-5 py-3 rounded-xl text-sm font-semibold bg-gray-100 text-gray-500 hover:bg-gray-200 transition-colors"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

interface LectureCandidateCardProps {
  lecture: Lecture;
  selected: boolean;
  onToggle: () => void;
}

function LectureCandidateCard({ lecture, selected, onToggle }: LectureCandidateCardProps) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className={`w-full text-left rounded-xl border-2 p-4 transition-all ${
          selected
            ? "border-blue-500 bg-blue-50 shadow-sm"
            : "border-gray-200 bg-white hover:border-blue-300"
        }`}
      >
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-800 line-clamp-2">{lecture.title}</p>
            {lecture.instructor_name && (
              <p className="text-xs text-gray-500 mt-0.5">{lecture.instructor_name}</p>
            )}
          </div>
          <div className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center ${
            selected ? "border-blue-500 bg-blue-500" : "border-gray-300"
          }`}>
            {selected && <span className="text-white text-xs">✓</span>}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-2">
          <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">{lecture.platform}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
            lecture.is_free ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
          }`}>
            {lecture.is_free ? "무료" : formatPrice(lecture.price)}
          </span>
          {lecture.rating != null && (
            <span className="text-xs px-2 py-0.5 bg-yellow-50 text-yellow-700 rounded-full">
              ★ {lecture.rating.toFixed(1)}
            </span>
          )}
          {lecture.student_count != null && (
            <span className="text-xs px-2 py-0.5 bg-gray-50 text-gray-500 rounded-full">
              {lecture.student_count.toLocaleString()}명
            </span>
          )}
        </div>

        <p className="text-xs text-blue-500 mt-1">자세히 보기 →</p>
      </button>

      {showModal && (
        <LectureDetailModal
          lecture={lecture}
          selected={selected}
          onToggle={onToggle}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}

interface StepSectionProps {
  group: StepGroup;
  stepTitle?: string;
  selectedIds: Set<number>;
  onToggle: (id: number) => void;
}

function StepSection({ group, stepTitle, selectedIds, onToggle }: StepSectionProps) {
  const selectedCount = group.candidates.filter((c) => selectedIds.has(c.id)).length;
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center font-bold flex-shrink-0">
          {group.step}
        </div>
        <h3 className="text-sm font-bold text-gray-800">{stepTitle ?? `${group.step}단계`}</h3>
        <span className="text-xs text-gray-400">
          {selectedCount > 0 ? `${selectedCount}개 선택됨` : "선택하세요"}
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {group.candidates.map((lec) => (
          <LectureCandidateCard
            key={lec.id}
            lecture={lec}
            selected={selectedIds.has(lec.id)}
            onToggle={() => onToggle(lec.id)}
          />
        ))}
      </div>
    </div>
  );
}

interface YtSupplementsProps {
  lectures: Lecture[];
}

function YtSupplements({ lectures }: YtSupplementsProps) {
  const [open, setOpen] = useState(false);
  if (!lectures.length) return null;
  return (
    <div className="mb-6">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-blue-600 transition-colors"
      >
        <span>🎬 유튜브 추천 영상</span>
        <span className="text-xs text-gray-400 font-normal">후기·공부법</span>
        <span className="text-xs text-blue-500">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {lectures.map((lec) => (
            <a
              key={lec.id}
              href={lec.url ?? "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-3 bg-red-50 border border-red-100 rounded-xl hover:bg-red-100 transition-colors"
            >
              <span className="text-lg">▶</span>
              <span className="text-xs text-gray-700 line-clamp-2">{lec.title}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

interface EmailPanelProps {
  question: string;
  roadmap: Roadmap;
  selectedLectures: Lecture[];
}

function EmailPanel({ question, roadmap, selectedLectures }: EmailPanelProps) {
  const [email, setEmail] = useState("kkhlhj485@gmail.com");
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");

  const send = async () => {
    if (!email.trim() || selectedLectures.length === 0) return;
    setStatus("sending");
    try {
      const res = await sendRecommendEmail({ question, email, roadmap, lectures: selectedLectures, certs: roadmap.recommended_certs });
      if (res.status === "ok") {
        setStatus("done");
        setMsg(res.message);
      } else {
        setStatus("error");
        setMsg(res.message);
      }
    } catch {
      setStatus("error");
      setMsg("전송 실패. 잠시 후 다시 시도해주세요.");
    }
  };

  return (
    <div className="mt-6 bg-blue-50 border border-blue-100 rounded-2xl p-4">
      <p className="text-sm font-semibold text-gray-700 mb-1">📧 선택한 강의를 이메일로 받기</p>
      {selectedLectures.length === 0 ? (
        <p className="text-xs text-amber-600 mb-3">강의를 1개 이상 선택해야 이메일을 보낼 수 있습니다.</p>
      ) : (
        <p className="text-xs text-gray-500 mb-3">
          선택된 강의 {selectedLectures.length}개 · 로드맵과 링크를 함께 보내드립니다.
        </p>
      )}
      <div className="flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => { setEmail(e.target.value); setStatus("idle"); }}
          placeholder="이메일 주소 입력"
          className="flex-1 px-3 py-2 border border-gray-200 rounded-xl bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          onClick={send}
          disabled={status === "sending" || !email.trim() || selectedLectures.length === 0}
          className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors whitespace-nowrap"
        >
          {status === "sending" ? "전송 중..." : "전송"}
        </button>
      </div>
      {status === "done" && <p className="text-xs text-green-600 mt-2">✅ {msg}</p>}
      {status === "error" && <p className="text-xs text-red-500 mt-2">❌ {msg}</p>}
    </div>
  );
}

export default function RecommendSection() {
  const [question, setQuestion] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const { mutate, data, isPending, isError } = useRecommend();

  const toggle = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const submit = (q: string) => {
    if (!q.trim()) return;
    setSelectedIds(new Set());
    mutate({ question: q.trim(), limit: 15 });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") submit(question);
  };

  const stepGroups = data?.step_groups ?? [];
  const ytSupplements = data?.yt_supplements ?? [];
  const roadmapSteps = data?.roadmap?.roadmap ?? [];

  const selectedLectures = stepGroups
    .flatMap((g) => g.candidates)
    .filter((lec) => selectedIds.has(lec.id));

  return (
    <section className="mb-10">
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-800 mb-1">AI 강의 추천</h2>
        <p className="text-sm text-gray-500 mb-4">원하는 걸 자유롭게 말해보세요 — AI가 로드맵을 설계하고 단계별 강의를 추천해드립니다</p>
        <div className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="예: 토익 처음인데 돈이 없어요, 파이썬 입문 5만원 이하..."
            className="flex-1 px-4 py-3 border border-gray-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 text-sm"
          />
          <button
            onClick={() => submit(question)}
            disabled={isPending || !question.trim()}
            className="px-5 py-3 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-40 transition-colors"
          >
            {isPending ? "설계 중..." : "추천받기"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => { setQuestion(ex); submit(ex); }}
              className="px-3 py-1 bg-white border border-gray-200 rounded-full text-xs text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {isPending && (
        <div className="text-center py-8 text-sm text-gray-400">
          <div className="animate-spin text-2xl mb-2">⟳</div>
          AI가 학습 로드맵을 설계하고 단계별 강의를 선별 중입니다... (30~60초 소요)
        </div>
      )}

      {isError && (
        <p className="text-red-500 text-sm text-center py-4">추천을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</p>
      )}

      {data && !isPending && (
        <div>
          {roadmapSteps.length > 0 && (
            <RoadmapCard
              steps={roadmapSteps}
              goal={data.roadmap.goal}
              level={data.roadmap.user_level}
            />
          )}

          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-700">단계별 강의 선택</span>
              <span className="text-xs text-gray-400">마음에 드는 강의를 골라보세요</span>
            </div>
            {selectedIds.size > 0 && (
              <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-medium">
                {selectedIds.size}개 선택됨
              </span>
            )}
          </div>

          {stepGroups.length > 0 ? (
            stepGroups.map((group) => {
              const stepMeta = roadmapSteps.find((s) => s.step === group.step);
              return (
                <StepSection
                  key={group.step}
                  group={group}
                  stepTitle={stepMeta?.title}
                  selectedIds={selectedIds}
                  onToggle={toggle}
                />
              );
            })
          ) : (
            <p className="text-gray-400 text-sm text-center py-8">
              조건에 맞는 강의가 없습니다. 다른 표현으로 다시 시도해보세요.
            </p>
          )}

          <YtSupplements lectures={ytSupplements} />

          <EmailPanel
            question={data.question}
            roadmap={data.roadmap}
            selectedLectures={selectedLectures}
          />
        </div>
      )}
    </section>
  );
}
