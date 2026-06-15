"""유튜브 무료 강의 수집 — YouTube Data API v3.

방식: 카테고리 키워드로 검색 → 상위 영상/플레이리스트를 강의로 저장.
특정 채널 고정 없이 실제 검색 결과 기반 수집.
"""
import os
import requests
from app.db.queries import upsert_lecture, upsert_instructor
from app.db.models import LectureCreate
from app.utils.logger import logger

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
VIDEO_URL   = "https://www.googleapis.com/youtube/v3/videos"

# 검색 키워드: (카테고리, 검색어, 결과 수)
SEARCH_QUERIES = [
    # IT/개발
    ("IT/개발",      "파이썬 강의 무료",         50),
    ("IT/개발",      "자바스크립트 강의",          50),
    ("IT/개발",      "스프링 강의",               50),
    ("IT/개발",      "리액트 강의",               50),
    ("IT/개발",      "AWS 강의 무료",             50),
    ("IT/개발",      "알고리즘 강의 입문",         50),
    ("IT/개발",      "SQL 데이터베이스 강의",      50),
    ("IT/개발",      "머신러닝 딥러닝 강의",       50),
    ("IT/개발",      "코딩 입문 강의 초보",        50),
    ("IT/개발",      "클로드 AI 코딩 강의",        30),
    # 어학
    ("어학",         "토익 강의 무료",             50),
    ("어학",         "영어회화 강의 무료",          50),
    ("어학",         "오픽 강의 무료",             50),
    ("어학",         "텝스 강의",                 30),
    ("어학",         "일본어 강의 입문",           30),
    ("어학",         "중국어 강의 입문",           30),
    # 수능
    ("수능",         "수능 국어 강의 무료",         50),
    ("수능",         "수능 수학 강의 무료",         50),
    ("수능",         "수능 영어 강의 무료",         50),
    ("수능",         "수능 한국사 강의",            30),
    ("수능",         "수능 사탐 강의 무료",         30),
    # 공무원/자격증
    ("공무원/자격증","공무원 한국사 강의",          50),
    ("공무원/자격증","공무원 국어 강의",            30),
    ("공무원/자격증","정보처리기사 강의 무료",      30),
    ("공무원/자격증","컴퓨터활용능력 강의",         30),
    # 디자인/창작
    ("디자인/창작",  "포토샵 강의 무료 입문",       30),
    ("디자인/창작",  "일러스트 강의 입문",          30),
    ("디자인/창작",  "영상편집 강의 무료",          30),
    ("디자인/창작",  "피그마 강의 무료",            30),
    ("디자인/창작",  "드로잉 강의 입문 무료",       30),
    # 자기계발/비즈니스
    ("자기계발",     "엑셀 강의 무료 입문",         30),
    ("자기계발",     "PPT 강의 무료",              30),
    ("자기계발",     "독서법 강의",                20),
    # 재테크
    ("재테크",       "주식 강의 입문 무료",         30),
    ("재테크",       "부동산 강의 입문",            20),
    # 음악/악기
    ("음악",         "기타 강의 입문 무료",         20),
    ("음악",         "피아노 강의 입문 무료",       20),
    # 요리/취미
    ("요리/취미",    "요리 강의 기초",              20),
    ("요리/취미",    "베이킹 강의 입문",            20),
]


def collect_youtube_lectures() -> int:
    """키워드별 유튜브 검색 결과를 강의로 저장. 저장 건수 반환."""
    if not YOUTUBE_API_KEY:
        logger.error("YOUTUBE_API_KEY 환경변수 없음 — 유튜브 수집 건너뜀")
        return 0

    total = 0
    for category, query, max_results in SEARCH_QUERIES:
        try:
            count = _search_and_save(category, query, max_results)
            total += count
            logger.info(f"  [{category}] '{query}': {count}건")
        except Exception as e:
            logger.error(f"유튜브 검색 실패: '{query}' — {e}")

    logger.info(f"유튜브 강의 수집 완료: 총 {total}건")
    return total


def _search_and_save(category: str, query: str, max_results: int) -> int:
    """검색어로 유튜브 영상 검색 후 강의로 저장. 저장 건수 반환."""
    # 검색 (영상 + 재생목록 모두)
    items = _search_videos(query, max_results, type_filter="video") + \
            _search_videos(query, min(max_results, 20), type_filter="playlist")

    if not items:
        return 0

    # 영상 상세 정보 (조회수 등) 일괄 조회
    video_ids = [i["id"] for i in items if i["type"] == "video"]
    stats = _get_video_stats(video_ids) if video_ids else {}

    saved = 0
    seen_urls = set()
    for item in items:
        try:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            view_count = stats.get(item["id"], {}).get("viewCount")
            student_count = int(view_count) if view_count else None

            instructor = item.get("channel_title", "")
            if instructor:
                upsert_instructor(instructor, "youtube")

            upsert_lecture(LectureCreate(
                platform="youtube",
                title=item["title"][:200],
                instructor_name=instructor or None,
                category=category,
                price=0,
                rating=None,
                student_count=student_count,
                url=url,
                thumbnail_url=item.get("thumbnail"),
                tags=["무료", "유튜브"],
                is_free=True,
            ))
            saved += 1
        except Exception as e:
            logger.error(f"유튜브 저장 실패: {item.get('title', '')} — {e}")

    return saved


def _search_videos(query: str, max_results: int, type_filter: str = "video") -> list[dict]:
    """유튜브 검색 결과 반환."""
    try:
        resp = requests.get(SEARCH_URL, params={
            "key": YOUTUBE_API_KEY,
            "part": "snippet",
            "q": query,
            "maxResults": min(max_results, 50),
            "type": type_filter,
            "relevanceLanguage": "ko",
            "regionCode": "KR",
            "order": "relevance",
        }, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])

        result = []
        for item in items:
            snippet = item.get("snippet", {})
            id_obj = item.get("id", {})
            title = snippet.get("title", "")
            if not title:
                continue

            if type_filter == "video":
                vid_id = id_obj.get("videoId", "")
                if not vid_id:
                    continue
                url = f"https://www.youtube.com/watch?v={vid_id}"
                item_id = vid_id
            else:
                pl_id = id_obj.get("playlistId", "")
                if not pl_id:
                    continue
                url = f"https://www.youtube.com/playlist?list={pl_id}"
                item_id = pl_id

            result.append({
                "id": item_id,
                "type": type_filter,
                "title": title,
                "channel_title": snippet.get("channelTitle", ""),
                "url": url,
                "thumbnail": (snippet.get("thumbnails", {}).get("medium", {}) or {}).get("url"),
            })
        return result
    except Exception as e:
        logger.error(f"유튜브 검색 실패: {query} — {e}")
        return []


def _get_video_stats(video_ids: list[str]) -> dict[str, dict]:
    """영상 ID 목록의 통계 정보(조회수 등) 일괄 조회."""
    if not video_ids:
        return {}
    try:
        # 50개씩 배치 처리
        stats = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            resp = requests.get(VIDEO_URL, params={
                "key": YOUTUBE_API_KEY,
                "part": "statistics",
                "id": ",".join(batch),
            }, timeout=15)
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                stats[item["id"]] = item.get("statistics", {})
        return stats
    except Exception as e:
        logger.error(f"영상 통계 조회 실패: {e}")
        return {}


class YoutubeLectureCrawler:
    """crawl_all.py에서 호출하기 위한 래퍼 클래스."""

    async def crawl(self) -> list[dict]:
        import asyncio
        count = await asyncio.to_thread(collect_youtube_lectures)
        return [{}] * count
