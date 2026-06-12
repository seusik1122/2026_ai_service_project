interface LectureFilterProps {
  category: string;
  onCategoryChange: (v: string) => void;
  platform: string;
  onPlatformChange: (v: string) => void;
  isFree: boolean | undefined;
  onIsFreeChange: (v: boolean | undefined) => void;
}

const CATEGORIES = ["전체", "IT", "공무원", "자격증", "어학", "디자인"];
const PLATFORMS = ["전체", "inflearn", "class101", "fastcampus", "kmooc"];

export default function LectureFilter({
  category, onCategoryChange,
  platform, onPlatformChange,
  isFree, onIsFreeChange,
}: LectureFilterProps) {
  return (
    <div className="flex flex-wrap gap-3 mb-4">
      <select value={category} onChange={(e) => onCategoryChange(e.target.value)}
        className="border rounded px-3 py-1 text-sm">
        {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
      </select>
      <select value={platform} onChange={(e) => onPlatformChange(e.target.value)}
        className="border rounded px-3 py-1 text-sm">
        {PLATFORMS.map((p) => <option key={p}>{p}</option>)}
      </select>
      <select
        value={isFree === undefined ? "전체" : isFree ? "무료" : "유료"}
        onChange={(e) => {
          const v = e.target.value;
          onIsFreeChange(v === "전체" ? undefined : v === "무료");
        }}
        className="border rounded px-3 py-1 text-sm">
        <option>전체</option>
        <option>무료</option>
        <option>유료</option>
      </select>
    </div>
  );
}
