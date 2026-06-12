from datetime import datetime

from app.db.queries import get_reviews_by_instructor, update_instructor_trust_score
from app.db.models import InstructorUpdate
from app.utils.logger import logger


def calculate_trust_score(instructor_name: str) -> float:
    """강사 신뢰도 점수 계산 후 DB 업데이트. 계산된 점수 반환.

    계산식 (섹션 6):
        trust_score = (긍정 후기 수 / 전체 후기 수) * 60
                    + (평균 sentiment_score + 1) / 2 * 30
                    + min(전체 후기 수 / 100, 1.0) * 10
    후기가 없으면 0.0 반환.
    """
    reviews = get_reviews_by_instructor(instructor_name)

    scored = [r for r in reviews if r.get("sentiment_score") is not None]
    total = len(scored)

    if total == 0:
        logger.info(f"신뢰도 계산 불가 (후기 없음): {instructor_name}")
        return 0.0

    positive = sum(1 for r in scored if r["sentiment_score"] > 0)
    avg_score = sum(r["sentiment_score"] for r in scored) / total

    trust_score = (
        (positive / total) * 60
        + (avg_score + 1) / 2 * 30
        + min(total / 100, 1.0) * 10
    )
    trust_score = round(trust_score, 2)
    positive_ratio = round(positive / total, 4)

    try:
        update_instructor_trust_score(
            instructor_name,
            InstructorUpdate(
                trust_score=trust_score,
                positive_ratio=positive_ratio,
                review_count=total,
                last_calculated_at=datetime.now(),
            ),
        )
        logger.info(f"신뢰도 업데이트: {instructor_name} → {trust_score}")
    except Exception as e:
        logger.error(f"신뢰도 DB 업데이트 실패: {instructor_name} — {e}")

    return trust_score
