from typing import Optional
from fastapi import APIRouter
from app.db.queries import get_lectures, log_zapier_alert
from app.db.models import LectureRequest

router = APIRouter()


@router.get("/lectures")
async def search_lectures(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    is_free: Optional[bool] = None,
    platform: Optional[str] = None,
    sort: str = "rating",
    limit: int = 20,
):
    """강의 검색·추천 엔드포인트.

    sort: "rating" | "trust_score" | "student_count"
    """
    lectures = get_lectures(
        keyword=keyword,
        category=category,
        is_free=is_free,
        platform=platform,
        sort=sort,
        limit=limit,
    )
    return {"total": len(lectures), "lectures": lectures}


@router.post("/lectures/request")
async def request_lecture(body: LectureRequest):
    """Google Form → Zapier → 이 엔드포인트 → DB 저장 + Gmail 발송용 응답.

    Zapier Zap 4 흐름:
      Google Forms 응답 → POST /api/lectures/request → Gmail (email 필드 사용)
    """
    recommendations = get_lectures(keyword=body.topic, limit=5)

    payload = {
        "email": body.email,
        "topic": body.topic,
        "budget": body.budget,
        "level": body.level,
        "recommendations": [
            {"title": l["title"], "platform": l["platform"], "url": l.get("url", "")}
            for l in recommendations
        ],
    }
    log_zapier_alert("form_to_db", payload)

    return {
        "status": "ok",
        "email": body.email,
        "topic": body.topic,
        "recommendations": recommendations[:5],
    }
