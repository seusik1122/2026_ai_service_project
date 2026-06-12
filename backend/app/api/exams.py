from typing import Optional
from fastapi import APIRouter
from app.db.queries import get_exams

router = APIRouter()


@router.get("/exams")
async def search_exams(
    keyword: Optional[str] = None,
    d_day_within: Optional[int] = None,
):
    """자격증 시험 일정 조회.

    d_day_within: N일 이내 시험만 반환 (예: 30)
    """
    exams = get_exams(keyword=keyword, d_day_within=d_day_within)
    return {"exams": exams}
