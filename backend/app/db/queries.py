from datetime import date, datetime, timedelta
from app.db.supabase_client import supabase
from app.db.models import LectureCreate, ReviewCreate, InstructorUpdate, ExamCreate


# ── lectures 테이블 ──────────────────────────────────────

def upsert_lecture(data: LectureCreate) -> dict:
    """강의 저장. url 기준으로 중복 방지 (upsert)"""
    payload = data.model_dump()
    if payload.get("price") is None:
        payload["price"] = 0
    result = supabase.table("lectures").upsert(
        payload,
        on_conflict="url"
    ).execute()
    return result.data


def enrich_lecture(lecture_id: int, fields: dict) -> None:
    """강의 보강 데이터 부분 업데이트. None 값은 건너뜀."""
    payload = {k: v for k, v in fields.items() if v is not None}
    if not payload:
        return
    supabase.table("lectures").update(payload).eq("id", lecture_id).execute()


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


def search_lectures_multi(
    keywords: list[str] = None,
    categories: list[str] = None,
    is_free: bool = None,
    platforms: list[str] = None,
    max_price: int = None,
    sort: str = "student_count",
    limit: int = 20,
) -> list[dict]:
    """
    OR 검색: 다중 키워드를 단일 쿼리의 or_() 조건으로 묶어 실행.
    카테고리는 후처리 스코어링으로 관련 항목 우선 노출.
    """
    valid_sort = sort if sort in ("rating", "student_count", "price") else "student_count"
    kw_list = [kw for kw in (keywords or []) if kw][:5]

    def _fetch(plat_filter=None, extra_limit=60) -> list[dict]:
        q = supabase.table("lectures").select("*")
        if kw_list:
            or_filter = ",".join(f"title.ilike.%{kw}%" for kw in kw_list)
            q = q.or_(or_filter)
        if is_free is not None:
            q = q.eq("is_free", is_free)
        if max_price is not None:
            q = q.lte("price", max_price)
        if plat_filter:
            q = q.in_("platform", plat_filter)
        q = q.order(valid_sort, desc=(valid_sort != "price")).limit(extra_limit)
        return q.execute().data

    if platforms:
        rows = _fetch(plat_filter=platforms, extra_limit=60)
    else:
        # 유튜브 쏠림 방지: 유튜브 최대 10개 + 나머지 플랫폼 50개 합산
        NON_YOUTUBE = ["inflearn","fastcampus","class101","coloso","hackers",
                       "siwonschool","yanadoo","megastudy","ebsi","opentutorials","codeit"]
        yt_rows = _fetch(plat_filter=["youtube"], extra_limit=10)
        other_rows = _fetch(plat_filter=NON_YOUTUBE, extra_limit=50)
        seen_ids: set = set()
        rows = []
        for r in other_rows + yt_rows:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                rows.append(r)

    # 후처리: 원본 키워드 매칭 강도 + 카테고리 가중치로 정렬
    cat_set = set(categories or [])
    primary_kws = [kw.lower() for kw in (kw_list[:2] if kw_list else [])]  # 첫 2개가 핵심 키워드

    def _sort_key(x: dict) -> tuple:
        title = (x.get("title") or "").lower()
        # 핵심 키워드가 제목에 포함된 개수 (많을수록 관련성 높음)
        kw_match = sum(1 for kw in primary_kws if kw in title)
        in_cat = 1 if (cat_set and x.get("category") in cat_set) else 0
        if valid_sort == "rating":
            return (kw_match, in_cat, x.get("rating") or 0, x.get("student_count") or 0)
        elif valid_sort == "price":
            return (kw_match, in_cat, -(x.get("price") or 0))
        return (kw_match, in_cat, x.get("student_count") or 0)

    rows.sort(key=_sort_key, reverse=(valid_sort != "price"))
    return rows[:limit]


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
