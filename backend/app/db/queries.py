from datetime import date, datetime, timedelta
from app.db.supabase_client import supabase
from app.db.models import LectureCreate, ReviewCreate, InstructorUpdate, ExamCreate


# ── lectures 테이블 ──────────────────────────────────────

def upsert_lecture(data: LectureCreate) -> dict:
    """강의 저장. url 기준으로 중복 방지 (upsert)"""
    result = supabase.table("lectures").upsert(
        data.model_dump(),
        on_conflict="url"
    ).execute()
    return result.data


def get_lectures(
    keyword: str = None,
    category: str = None,
    is_free: bool = None,
    platform: str = None,
    sort: str = "rating",
    limit: int = 20
) -> list[dict]:
    """강의 검색. keyword는 title 대상 ILIKE 검색"""
    query = supabase.table("lectures").select("*")
    if keyword:
        query = query.ilike("title", f"%{keyword}%")
    if category:
        query = query.eq("category", category)
    if is_free is not None:
        query = query.eq("is_free", is_free)
    if platform:
        query = query.eq("platform", platform)
    query = query.order(sort, desc=True).limit(limit)
    return query.execute().data


# ── reviews 테이블 ───────────────────────────────────────

def insert_review(data: ReviewCreate) -> dict:
    """후기 저장. 중복 URL 체크 후 삽입"""
    result = supabase.table("reviews").upsert(
        data.model_dump(),
        on_conflict="original_url"
    ).execute()
    return result.data


def get_reviews_by_instructor(instructor_name: str) -> list[dict]:
    """특정 강사의 광고 아닌 후기 목록 반환"""
    return supabase.table("reviews") \
        .select("*") \
        .eq("instructor_name", instructor_name) \
        .eq("is_ad", False) \
        .order("collected_at", desc=True) \
        .execute().data


def get_unanalyzed_reviews() -> list[dict]:
    """감성 분석 안 된 후기 목록 반환 (sentiment가 NULL인 것)"""
    return supabase.table("reviews") \
        .select("*") \
        .is_("sentiment", "null") \
        .eq("is_ad", False) \
        .execute().data


def update_review_sentiment(review_id: str, sentiment: str, sentiment_score: float) -> dict:
    """감성 분석 결과를 reviews 테이블에 업데이트"""
    result = supabase.table("reviews") \
        .update({"sentiment": sentiment, "sentiment_score": sentiment_score}) \
        .eq("id", review_id) \
        .execute()
    return result.data


# ── instructors 테이블 ───────────────────────────────────

def upsert_instructor(name: str, platform: str) -> dict:
    """강사 최초 등록. name + platform 조합으로 중복 방지"""
    result = supabase.table("instructors").upsert(
        {"name": name, "platform": platform},
        on_conflict="name,platform"
    ).execute()
    return result.data


def update_instructor_trust_score(name: str, data: InstructorUpdate) -> dict:
    """AI 분석 완료 후 강사 신뢰도 점수 업데이트"""
    payload = data.model_dump()
    payload["last_calculated_at"] = payload["last_calculated_at"].isoformat()
    result = supabase.table("instructors") \
        .update(payload) \
        .eq("name", name) \
        .execute()
    return result.data


def get_instructor(name: str) -> dict | None:
    """강사 상세 정보 반환. 없으면 None."""
    result = supabase.table("instructors") \
        .select("*") \
        .eq("name", name) \
        .limit(1) \
        .execute()
    return result.data[0] if result.data else None


def get_instructors_with_score_change(threshold: float = 10.0) -> list[dict]:
    """지난 7일 대비 trust_score가 threshold 이상 변동된 강사 목록 반환"""
    instructors = supabase.table("instructors") \
        .select("*") \
        .execute().data

    result = []
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    for instructor in instructors:
        name = instructor["name"]
        current_score = instructor.get("trust_score") or 0

        old_reviews = supabase.table("reviews") \
            .select("sentiment_score") \
            .eq("instructor_name", name) \
            .eq("is_ad", False) \
            .lt("collected_at", week_ago) \
            .execute().data

        if not old_reviews:
            continue

        positive_old = sum(1 for r in old_reviews if r.get("sentiment_score") and r["sentiment_score"] > 0)
        total_old = len(old_reviews)
        avg_score_old = sum(
            r["sentiment_score"] for r in old_reviews if r.get("sentiment_score")
        ) / total_old

        old_trust_score = (positive_old / total_old) * 60 \
            + (avg_score_old + 1) / 2 * 30 \
            + min(total_old / 100, 1.0) * 10

        change = current_score - old_trust_score

        if abs(change) >= threshold:
            result.append({
                "instructor_name": name,
                "current_score": round(current_score, 1),
                "previous_score": round(old_trust_score, 1),
                "change": round(change, 1),
                "direction": "상승" if change > 0 else "하락"
            })

    return sorted(result, key=lambda x: abs(x["change"]), reverse=True)


# ── exams 테이블 ─────────────────────────────────────────

def upsert_exam(data: ExamCreate) -> dict:
    """시험 일정 저장. exam_name + exam_type 조합으로 중복 방지"""
    result = supabase.table("exams").upsert(
        data.model_dump(),
        on_conflict="exam_name,exam_type"
    ).execute()
    return result.data


def get_exams(keyword: str = None, d_day_within: int = None) -> list[dict]:
    """시험 일정 조회. d_day_within은 N일 이내 시험만 필터"""
    query = supabase.table("exams").select("*")
    if d_day_within is not None:
        query = query.lte("d_day", d_day_within).gte("d_day", 0).order("d_day")
    rows = query.execute().data
    if keyword:
        keyword_lower = keyword.lower()
        rows = [r for r in rows if keyword_lower in r["exam_name"].lower()]
    return rows


def update_exam_dday() -> None:
    """매일 실행. 모든 시험의 d_day를 오늘 기준으로 재계산"""
    exams = supabase.table("exams").select("id, exam_date").execute().data
    today = date.today()
    for exam in exams:
        if exam["exam_date"]:
            exam_date = date.fromisoformat(exam["exam_date"])
            d_day = (exam_date - today).days
            supabase.table("exams").update({"d_day": d_day}).eq("id", exam["id"]).execute()


# ── zapier_alerts_log 테이블 ─────────────────────────────

def log_zapier_alert(alert_type: str, payload: dict) -> dict:
    """Zapier 알림 발송 이력 저장"""
    result = supabase.table("zapier_alerts_log").insert({
        "alert_type": alert_type,
        "payload": payload
    }).execute()
    return result.data
