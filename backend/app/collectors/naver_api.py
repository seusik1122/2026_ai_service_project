# 네이버 검색 API 수집기 (블로그 후기)
# 명세서 섹션 5:
#   검색 쿼리 패턴: "{강사명} 강의 후기"
#   엔드포인트: https://openapi.naver.com/v1/search/blog.json
#   파라미터: query, display=100(최대), sort=date(최신순)
#   헤더: X-Naver-Client-Id / X-Naver-Client-Secret
#   저장: insert_review() 호출 (platform_source='naver_blog')
import os

import requests

from app.db.queries import insert_review
from app.db.models import ReviewCreate
from app.utils.text_cleaner import clean_text, truncate
from app.utils.logger import logger

BLOG_API_URL = "https://openapi.naver.com/v1/search/blog.json"
DISPLAY_MAX = 100


def collect_naver_reviews(instructor_name: str, display: int = DISPLAY_MAX) -> list[ReviewCreate]:
    """강사명으로 네이버 블로그 후기를 수집해 insert_review()로 저장.

    저장에 성공한 ReviewCreate 목록을 반환한다.
    """
    query = f"{instructor_name} 강의 후기"
    headers = {
        "X-Naver-Client-Id": os.getenv("NAVER_CLIENT_ID"),
        "X-Naver-Client-Secret": os.getenv("NAVER_CLIENT_SECRET"),
    }
    params = {"query": query, "display": display, "sort": "date"}

    try:
        resp = requests.get(BLOG_API_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception as e:
        logger.error(f"네이버 API 실패: {instructor_name} — {e}")
        return []

    saved: list[ReviewCreate] = []
    for item in items:
        # 제목 + 본문 요약을 합쳐 HTML 태그(<b> 등) 제거 후 500자 truncate
        raw = f"{item.get('title', '')} {item.get('description', '')}"
        content = truncate(clean_text(raw))
        if not content:
            continue

        review = ReviewCreate(
            instructor_name=instructor_name,
            platform_source="naver_blog",
            content=content,
            original_url=item.get("link"),
        )
        try:
            insert_review(review)
            saved.append(review)
        except Exception as e:
            logger.error(f"후기 저장 실패: {item.get('link')} — {e}")

    logger.info(f"네이버 후기 수집 완료: {instructor_name} — {len(saved)}건")
    return saved
