import { useState } from "react";
import { Link } from "react-router-dom";
import SearchBar from "../components/common/SearchBar";
import LoadingSpinner from "../components/common/LoadingSpinner";
import LectureFilter from "../components/lecture/LectureFilter";
import LectureList from "../components/lecture/LectureList";
import { useLectures } from "../hooks/useLectures";

export default function HomePage() {
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("전체");
  const [platform, setPlatform] = useState("전체");
  const [isFree, setIsFree] = useState<boolean | undefined>(undefined);

  const { data, isLoading, isError } = useLectures({
    keyword: keyword || undefined,
    category: category === "전체" ? undefined : category,
    platform: platform === "전체" ? undefined : platform,
    is_free: isFree,
    limit: 40,
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">강의 통합 추천</h1>
        <Link to="/dashboard" className="text-sm text-blue-600 hover:underline">
          대시보드 →
        </Link>
      </header>

      <div className="mb-4">
        <SearchBar value={keyword} onChange={setKeyword} placeholder="강의 검색" />
      </div>

      <LectureFilter
        category={category}
        onCategoryChange={setCategory}
        platform={platform}
        onPlatformChange={setPlatform}
        isFree={isFree}
        onIsFreeChange={setIsFree}
      />

      {isLoading && <LoadingSpinner />}
      {isError && <p className="text-red-500 text-sm py-8 text-center">강의를 불러오지 못했습니다.</p>}
      {data && (
        <>
          <p className="text-gray-500 text-sm mb-3">총 {data.total}개</p>
          {data.lectures.length > 0 ? (
            <LectureList lectures={data.lectures} />
          ) : (
            <p className="text-gray-400 text-sm py-8 text-center">검색 결과가 없습니다.</p>
          )}
        </>
      )}
    </div>
  );
}
