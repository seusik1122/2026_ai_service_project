import { useState } from "react";
import { Lecture } from "../../types/lecture";
import LectureCard from "./LectureCard";
import LectureDetailModal from "./LectureDetailModal";

interface LectureListProps {
  lectures: Lecture[];
  question?: string;
}

export default function LectureList({ lectures, question = "" }: LectureListProps) {
  const [selected, setSelected] = useState<Lecture | null>(null);

  const supplements = lectures.filter((l) => l.roadmap_step === 0);
  const main = lectures.filter((l) => l.roadmap_step !== 0);

  return (
    <>
      {supplements.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-sm font-semibold text-gray-700">🎬 유튜브 추천 영상</span>
            <span className="text-xs text-gray-400">후기 · 공부법 · 합격수기</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {supplements.map((l) => (
              <LectureCard key={l.id} lecture={l} onClick={setSelected} />
            ))}
          </div>
        </div>
      )}

      {main.length > 0 && (
        <div>
          {supplements.length > 0 && (
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-semibold text-gray-700">📚 로드맵 추천 강의</span>
              <span className="text-xs text-gray-400">단계별 학습 커리큘럼</span>
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {main.map((l) => (
              <LectureCard key={l.id} lecture={l} onClick={setSelected} />
            ))}
          </div>
        </div>
      )}

      {selected && (
        <LectureDetailModal
          lecture={selected}
          question={question}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
