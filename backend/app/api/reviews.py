from fastapi import APIRouter
from app.db.queries import get_reviews_by_instructor

router = APIRouter()


@router.get("/reviews/{instructor_name}")
async def get_reviews(instructor_name: str):
    """특정 강사의 광고 아닌 후기 목록 반환."""
    reviews = get_reviews_by_instructor(instructor_name)
    return {"total": len(reviews), "reviews": reviews}
