import { Lecture } from "../../types/lecture";

interface LectureCardProps {
  lecture: Lecture;
  onClick?: (lecture: Lecture) => void;
}

export default function LectureCard({ lecture, onClick }: LectureCardProps) {
  const displayPrice = lecture.is_free
    ? "무료"
    : lecture.price > 0
    ? `${lecture.price.toLocaleString()}원`
    : "가격 확인 필요";

  return (
    <div
      className="border rounded-xl p-4 hover:shadow-md transition-shadow cursor-pointer hover:border-blue-300 flex flex-col gap-2"
      onClick={() => onClick?.(lecture)}
    >
      {lecture.thumbnail_url && (
        <img src={lecture.thumbnail_url} alt={lecture.title} className="w-full h-36 object-cover rounded-lg" />
      )}
      <h3 className="font-semibold text-sm line-clamp-2 leading-snug">{lecture.title}</h3>
      {lecture.reason && (
        <p className="text-xs text-blue-600 bg-blue-50 rounded-lg px-2 py-1.5 line-clamp-2 leading-relaxed">
          💡 {lecture.reason}
        </p>
      )}
      <div className="flex items-center justify-between mt-auto">
        <span className={`font-bold text-sm ${lecture.is_free ? "text-green-600" : "text-blue-600"}`}>
          {displayPrice}
        </span>
        <span className="text-xs text-gray-400">{lecture.platform}</span>
      </div>
    </div>
  );
}
