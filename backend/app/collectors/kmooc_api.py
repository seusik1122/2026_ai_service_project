# K-MOOC 무료강의 수집기 (Open edX courses API)
# 명세서 섹션 5:
#   엔드포인트: https://www.kmooc.kr/api/courses/v1/courses/
#   파라미터: page_size=100, org(기관 필터, 선택)
#   저장: upsert_lecture() 호출 (platform='kmooc', is_free=True)
from typing import Optional

import requests

from app.db.queries import upsert_lecture
from app.db.models import LectureCreate
from app.utils.text_cleaner import clean_text
from app.utils.logger import logger

KMOOC_API_URL = "https://www.kmooc.kr/api/courses/v1/courses/"
COURSE_BASE = "https://www.kmooc.kr/courses"
SITE_BASE = "https://www.kmooc.kr"
PAGE_SIZE = 100
MAX_PAGES = 20  # 페이지네이션 무한루프 방지 안전장치


def collect_kmooc_lectures(org: Optional[str] = None) -> int:
    """K-MOOC 무료 강의를 수집해 upsert_lecture(platform='kmooc', is_free=True). 저장 건수 반환."""
    params: dict = {"page_size": PAGE_SIZE}
    if org:
        params["org"] = org

    saved = 0
    url = KMOOC_API_URL
    for _ in range(MAX_PAGES):
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"K-MOOC API 실패: {e}")
            break

        for course in data.get("results", []):
            try:
                lecture = _to_lecture(course)
                if not lecture.title:
                    continue
                upsert_lecture(lecture)
                saved += 1
            except Exception as e:
                logger.error(f"K-MOOC 저장 실패: {course.get('course_id')} — {e}")

        # edX courses API 페이지네이션: pagination.next 가 있으면 이어서 수집
        next_url = (data.get("pagination") or {}).get("next")
        if not next_url:
            break
        url = next_url
        params = {}  # next URL 에 쿼리스트링이 이미 포함됨

    logger.info(f"K-MOOC 수집 완료: {saved}건")
    return saved


def _to_lecture(course: dict) -> LectureCreate:
    """edX course 객체 → LectureCreate 매핑."""
    course_id = course.get("course_id", "")

    media = course.get("media") or {}
    image = media.get("course_image") or media.get("image") or {}
    thumbnail = image.get("uri") or image.get("raw") or None
    if thumbnail and thumbnail.startswith("/"):
        thumbnail = f"{SITE_BASE}{thumbnail}"

    # course_id 는 'course-v1:Org+Num+Run' 형태라 그대로 URL이 아님 → about 페이지로 구성
    url = f"{COURSE_BASE}/{course_id}/about" if course_id else None

    return LectureCreate(
        platform="kmooc",
        title=clean_text(course.get("name", "")),
        instructor_name=course.get("org") or None,  # edX는 강사명 미제공 → 기관명으로 대체
        category=None,
        url=url,
        thumbnail_url=thumbnail,
        is_free=True,
        price=0,
    )
