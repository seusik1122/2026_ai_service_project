"""강의 DB에서 강사 자동 추출 → YouTube 수집 → 광고필터 → 감성분석 → 신뢰도 계산."""
import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.collectors.youtube_api import collect_youtube_reviews
from app.db.queries import get_unanalyzed_reviews, update_review_sentiment, upsert_instructor
from app.ai.ad_filter import filter_ad
from app.ai.sentiment import analyze_sentiment
from app.ai.trust_score import calculate_trust_score
from app.utils.logger import logger
from app.db.supabase_client import supabase

MAX_REVIEWS_PER_INSTRUCTOR = 500


def get_instructors_from_db() -> list[tuple[str, str]]:
    """lectures 테이블에서 실존 강사명 자동 추출."""
    result = supabase.table("lectures").select("instructor_name, platform").execute()
    seen = set()
    instructors = []
    for row in result.data:
        name = row.get("instructor_name")
        platform = row.get("platform", "unknown")
        if name and name not in seen:
            seen.add(name)
            instructors.append((name, platform))
    return instructors


async def analyze_reviews():
    # 1. DB에서 강사 자동 추출
    instructors = get_instructors_from_db()
    print(f"\n[강사 목록] DB에서 {len(instructors)}명 추출")
    for name, platform in instructors:
        print(f"  {name} ({platform})")

    # 2. YouTube 댓글 수집
    print("\n[1단계] YouTube 댓글 수집")
    for name, platform in instructors:
        upsert_instructor(name, platform)
        count = collect_youtube_reviews(name)
        print(f"  {name}: {count}개 수집")

    # 3. 광고 필터링 + 감성 분석 (강사당 MAX_REVIEWS_PER_INSTRUCTOR개 제한)
    print("\n[2단계] 광고 필터링 + 감성 분석")
    reviews = get_unanalyzed_reviews()
    # 강사당 제한 적용
    from collections import Counter
    instructor_count: Counter = Counter()
    filtered = []
    for r in reviews:
        name = r.get("instructor_name") or "unknown"
        if instructor_count[name] < MAX_REVIEWS_PER_INSTRUCTOR:
            filtered.append(r)
            instructor_count[name] += 1
    print(f"  분석 대상: {len(filtered)}개 (강사당 최대 {MAX_REVIEWS_PER_INSTRUCTOR}개)")

    for i, review in enumerate(filtered):
        try:
            ad_result = await filter_ad(review["content"])
            if ad_result.get("is_ad"):
                update_review_sentiment(review["id"], "neutral", 0.0)
                continue

            result = await analyze_sentiment(review["content"])
            update_review_sentiment(review["id"], result["sentiment"], result["score"])

            if (i + 1) % 50 == 0:
                print(f"  진행: {i+1}/{len(filtered)}")
        except Exception as e:
            logger.error(f"분석 실패: {review['id']} — {e}")

    # 4. 신뢰도 점수 계산
    print("\n[3단계] 강사 신뢰도 점수 계산")
    for name, _ in instructors:
        score = calculate_trust_score(name)
        if score > 0:
            print(f"  {name}: 신뢰도 {score:.1f}점")

    # 최종 현황
    print("\n=== 최종 DB 현황 ===")
    for table in ["lectures", "reviews", "instructors"]:
        count = supabase.table(table).select("id", count="exact").execute().count
        print(f"  {table}: {count}개")

    print("\n=== 완료 ✅ ===")

if __name__ == "__main__":
    asyncio.run(analyze_reviews())
