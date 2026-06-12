import { Lecture } from "../../types/lecture";

interface LectureCardProps {
  lecture: Lecture;
}

export default function LectureCard({ lecture }: LectureCardProps) {
  const displayPrice =
    lecture.price === -1
      ? "가격 확인 필요"
      : lecture.price === 0
      ? "무료"
      : `${lecture.price.toLocaleString()}원`;

  return (
    <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
      {lecture.thumbnail_url && (
        <img src={lecture.thumbnail_url} alt={lecture.title} className="w-full h-40 object-cover rounded mb-3" />
      )}
      <h3 className="font-semibold text-sm line-clamp-2">{lecture.title}</h3>
      <p className="text-gray-500 text-xs mt-1">{lecture.instructor_name}</p>
      <div className="flex items-center justify-between mt-2">
        <span className="text-blue-600 font-bold text-sm">{displayPrice}</span>
        {lecture.trust_score !== undefined && (
          <span className="text-xs text-gray-400">신뢰도 {lecture.trust_score.toFixed(0)}</span>
        )}
      </div>
    </div>
  );
}
