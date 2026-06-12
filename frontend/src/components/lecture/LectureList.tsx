import { Lecture } from "../../types/lecture";
import LectureCard from "./LectureCard";

interface LectureListProps {
  lectures: Lecture[];
}

export default function LectureList({ lectures }: LectureListProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {lectures.map((l) => (
        <LectureCard key={l.id} lecture={l} />
      ))}
    </div>
  );
}
