# YouTube Data API v3 수집기 (영상 댓글 후기)
# 명세서 섹션 5:
#   검색 쿼리 패턴: "{강사명} 강의 리뷰"
#   엔드포인트: search.list(영상 검색, 최신 50개) → commentThreads.list(댓글, 최대 100개)
#   파라미터: key, part=snippet, maxResults, relevanceLanguage=ko
#   저장: insert_review() 호출 (platform_source='youtube_comment')
import os

import requests

from app.db.queries import insert_review
from app.db.models import ReviewCreate
from app.utils.text_cleaner import clean_text, truncate
from app.utils.logger import logger

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
SEARCH_MAX = 50
COMMENTS_MAX = 100


def collect_youtube_reviews(instructor_name: str) -> int:
    """강사명으로 YouTube 영상을 검색하고 각 영상의 댓글을 수집·저장. 저장 건수 반환."""
    query = f"{instructor_name} 강의 리뷰"
    params = {
        "key": os.getenv("YOUTUBE_API_KEY"),
        "part": "snippet",
        "q": query,
        "maxResults": SEARCH_MAX,
        "relevanceLanguage": "ko",
        "type": "video",
    }
    try:
        resp = requests.get(SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        videos = resp.json().get("items", [])
    except Exception as e:
        logger.error(f"YouTube API 실패: {instructor_name} — {e}")
        return 0

    total = 0
    for video in videos:
        video_id = video.get("id", {}).get("videoId")
        if not video_id:
            continue
        total += _collect_comments(instructor_name, video_id)
    logger.info(f"YouTube 수집 완료: {instructor_name} — 댓글 {total}건")
    return total


def _collect_comments(instructor_name: str, video_id: str) -> int:
    """단일 영상의 최상위 댓글을 수집·저장. 저장 건수 반환."""
    params = {
        "key": os.getenv("YOUTUBE_API_KEY"),
        "part": "snippet",
        "videoId": video_id,
        "maxResults": COMMENTS_MAX,
    }
    try:
        resp = requests.get(COMMENTS_URL, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception as e:
        logger.error(f"YouTube 댓글 실패: {video_id} — {e}")
        return 0

    saved = 0
    for item in items:
        try:
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            # textDisplay 에는 <br>, <a>, &quot; 등 HTML 이 섞임 → 정제 후 500자 truncate
            content = truncate(clean_text(snippet.get("textDisplay", "")))
            if not content:
                continue

            # 댓글별 고유 URL. insert_review 는 original_url 로 upsert 하므로
            # 영상 URL을 공유하면 같은 영상 댓글이 서로 덮어써진다 → lc=댓글ID 로 고유화.
            comment_id = item.get("id", "")
            comment_url = f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"

            insert_review(ReviewCreate(
                instructor_name=instructor_name,
                platform_source="youtube_comment",
                content=content,
                original_url=comment_url,
            ))
            saved += 1
        except Exception as e:
            logger.error(f"댓글 처리 실패: {video_id} — {e}")
    return saved
