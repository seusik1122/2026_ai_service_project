from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI
import os
from app.db.queries import get_lectures, log_zapier_alert
from app.db.models import LectureRequest
from app.db.supabase_client import supabase
from app.utils.logger import logger

router = APIRouter()


@router.get("/lectures/{lecture_id}/detail")
async def get_lecture_detail(lecture_id: int):
    """강의 상세 정보 + 강사 신뢰도 + 관련 후기 3건."""
    rows = supabase.table("lectures").select("*").eq("id", lecture_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="강의를 찾을 수 없습니다.")
    lecture = rows[0]

    instructor_name = lecture.get("instructor_name")
    instructor = None
    reviews = []

    if instructor_name:
        inst_rows = supabase.table("instructors").select("*").eq("name", instructor_name).limit(1).execute().data
        if inst_rows:
            instructor = inst_rows[0]

        rev_rows = (
            supabase.table("reviews")
            .select("*")
            .eq("instructor_name", instructor_name)
            .eq("is_ad", False)
            .order("collected_at", desc=True)
            .limit(3)
            .execute()
            .data
        )
        reviews = rev_rows

    return {
        "lecture": lecture,
        "instructor": instructor,
        "reviews": reviews,
    }


class WhyRequest(BaseModel):
    question: str = ""


@router.post("/lectures/{lecture_id}/why")
async def explain_why(lecture_id: int, body: WhyRequest):
    """GPT가 이 강의를 추천하는 이유 2~3줄 생성."""
    rows = supabase.table("lectures").select("*").eq("id", lecture_id).limit(1).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="강의를 찾을 수 없습니다.")
    lec = rows[0]

    system_prompt = (
        "너는 국내 온라인 강의 추천 전문가야. "
        "사용자의 구체적인 목적과 이 강의가 어떻게 맞는지 2~3문장으로 설명해. "
        "반드시 다음 규칙을 따라:\n"
        "1. '사용자가 원하는 것'과 '이 강의가 제공하는 것'의 연결고리를 명확히 써.\n"
        "2. 수강생 수나 평점 같은 수치가 있으면 구체적으로 언급해. 없으면 제목·플랫폼 특성으로 대체해.\n"
        "3. 이 강의만의 차별점(커리큘럼 특징, 대상 수준, 접근 방식)을 강의 제목에서 유추해서 써.\n"
        "4. '적합합니다', '도와줍니다' 같은 막연한 표현 금지. 구체적으로 써.\n"
        "5. 2~3문장 이내로 간결하게."
    )

    student_count = lec.get('student_count')
    rating = lec.get('rating')
    price = '무료' if lec.get('is_free') else str(lec.get('price', 0)) + '원'

    user_content = (
        f"사용자 질문: {body.question or '좋은 강의 추천'}\n\n"
        f"강의 정보:\n"
        f"- 제목: {lec.get('title')}\n"
        f"- 강사: {lec.get('instructor_name', '미상')}\n"
        f"- 플랫폼: {lec.get('platform')}\n"
        f"- 카테고리: {lec.get('category', '없음')}\n"
        f"- 평점: {f'{rating}점' if rating else '없음'}\n"
        f"- 수강생 수: {f'{student_count:,}명' if student_count else '없음'}\n"
        f"- 가격: {price}\n\n"
        f"위 강의가 사용자 질문에 왜 적합한지, 차별점을 포함해 2~3문장으로 설명해."
    )

    try:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = await client.chat.completions.create(
            model="gpt-5.5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_completion_tokens=200,
        )
        reason = resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"why 생성 실패: {e}")
        reason = f"'{lec.get('title')}' 강의는 {lec.get('platform')} 플랫폼에서 제공되며, 관련 주제를 학습하기에 적합합니다."

    return {"lecture_id": lecture_id, "reason": reason}


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
