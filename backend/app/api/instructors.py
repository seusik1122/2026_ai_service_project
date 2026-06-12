from typing import Optional
from fastapi import APIRouter, HTTPException
from app.db.queries import get_instructor, get_reviews_by_instructor, get_instructors_with_score_change

router = APIRouter()


@router.get("/instructors/trend")
async def get_instructor_trend(threshold: float = 10.0):
    """신뢰도 점수가 threshold 이상 변동된 강사 목록 반환 (Zapier Zap 3용)."""
    result = get_instructors_with_score_change(threshold=threshold)
    return {"instructors": result}


@router.get("/instructors/{instructor_name}")
async def get_instructor_detail(instructor_name: str):
    """강사 신뢰도 점수 + 최근 후기 반환."""
    instructor = get_instructor(instructor_name)
    if not instructor:
        raise HTTPException(status_code=404, detail="강사를 찾을 수 없습니다.")
    reviews = get_reviews_by_instructor(instructor_name)
    return {**instructor, "recent_reviews": reviews[:10]}
