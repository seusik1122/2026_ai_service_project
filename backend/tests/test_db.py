"""
DB 레이어 테스트.
실제 Supabase에 연결해서 테스트한다. .env에 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 필요.
테스트 데이터는 테스트 종료 후 자동 삭제된다.
"""
import pytest
from datetime import datetime
from app.db.queries import (
    upsert_lecture,
    get_lectures,
    insert_review,
    get_reviews_by_instructor,
    get_unanalyzed_reviews,
    update_review_sentiment,
    upsert_instructor,
    update_instructor_trust_score,
    get_instructor,
    upsert_exam,
    get_exams,
    update_exam_dday,
    log_zapier_alert,
)
from app.db.models import LectureCreate, ReviewCreate, InstructorUpdate, ExamCreate
from app.db.supabase_client import supabase

TEST_URL = "https://test.example.com/lecture-db-test"
TEST_INSTRUCTOR = "testinstructor"
TEST_EXAM = "testexam"


@pytest.fixture(autouse=True)
def cleanup():
    """각 테스트 전후 테스트 데이터 삭제"""
    yield
    supabase.table("lectures").delete().eq("url", TEST_URL).execute()
    supabase.table("reviews").delete().eq("instructor_name", TEST_INSTRUCTOR).execute()
    supabase.table("instructors").delete().eq("name", TEST_INSTRUCTOR).execute()
    supabase.table("exams").delete().eq("exam_name", TEST_EXAM).execute()


# ── lectures ─────────────────────────────────────────────

def test_upsert_lecture_creates_new():
    data = LectureCreate(
        platform="inflearn",
        title="테스트 강의",
        instructor_name=TEST_INSTRUCTOR,
        category="IT",
        price=10000,
        url=TEST_URL,
        is_free=False,
    )
    result = upsert_lecture(data)
    assert result is not None


def test_upsert_lecture_deduplicates_by_url():
    data = LectureCreate(platform="inflearn", title="중복 테스트", url=TEST_URL)
    upsert_lecture(data)
    upsert_lecture(data)  # 동일 URL 두 번 — 중복 없이 upsert 돼야 함
    rows = supabase.table("lectures").select("*").eq("url", TEST_URL).execute().data
    assert len(rows) == 1


def test_get_lectures_keyword_filter():
    upsert_lecture(LectureCreate(platform="inflearn", title="파이썬 기초", url=TEST_URL))
    result = get_lectures(keyword="파이썬")
    titles = [r["title"] for r in result]
    assert "파이썬 기초" in titles


def test_get_lectures_is_free_filter():
    upsert_lecture(LectureCreate(platform="kmooc", title="무료강의", url=TEST_URL, is_free=True))
    result = get_lectures(is_free=True)
    assert all(r["is_free"] for r in result)


# ── reviews ──────────────────────────────────────────────

def test_insert_review_creates_new():
    data = ReviewCreate(
        instructor_name=TEST_INSTRUCTOR,
        platform_source="naver_blog",
        content="정말 좋은 강의입니다.",
        original_url="https://test.example.com/review-1",
    )
    result = insert_review(data)
    assert result is not None


def test_get_reviews_by_instructor_excludes_ads():
    insert_review(ReviewCreate(
        instructor_name=TEST_INSTRUCTOR,
        platform_source="naver_blog",
        content="진짜 후기",
        is_ad=False,
        original_url="https://test.example.com/review-real",
    ))
    insert_review(ReviewCreate(
        instructor_name=TEST_INSTRUCTOR,
        platform_source="naver_blog",
        content="광고 후기",
        is_ad=True,
        original_url="https://test.example.com/review-ad",
    ))
    result = get_reviews_by_instructor(TEST_INSTRUCTOR)
    assert all(not r["is_ad"] for r in result)


def test_get_unanalyzed_reviews_returns_null_sentiment():
    insert_review(ReviewCreate(
        instructor_name=TEST_INSTRUCTOR,
        platform_source="youtube_comment",
        content="분석 안 된 후기",
        original_url="https://test.example.com/review-unanalyzed",
    ))
    result = get_unanalyzed_reviews()
    assert any(r["instructor_name"] == TEST_INSTRUCTOR for r in result)


def test_update_review_sentiment():
    insert_review(ReviewCreate(
        instructor_name=TEST_INSTRUCTOR,
        platform_source="naver_blog",
        content="감성 업데이트 테스트",
        original_url="https://test.example.com/review-sentiment",
    ))
    rows = supabase.table("reviews").select("id").eq("instructor_name", TEST_INSTRUCTOR).execute().data
    review_id = rows[0]["id"]
    update_review_sentiment(review_id, "positive", 0.9)
    updated = supabase.table("reviews").select("sentiment, sentiment_score").eq("id", review_id).single().execute().data
    assert updated["sentiment"] == "positive"
    assert updated["sentiment_score"] == 0.9


# ── instructors ──────────────────────────────────────────

def test_upsert_instructor_creates_new():
    result = upsert_instructor(TEST_INSTRUCTOR, "inflearn")
    assert result is not None


def test_upsert_instructor_deduplicates():
    upsert_instructor(TEST_INSTRUCTOR, "inflearn")
    upsert_instructor(TEST_INSTRUCTOR, "inflearn")
    rows = supabase.table("instructors").select("*").eq("name", TEST_INSTRUCTOR).execute().data
    assert len(rows) == 1


def test_update_instructor_trust_score():
    upsert_instructor(TEST_INSTRUCTOR, "inflearn")
    data = InstructorUpdate(
        trust_score=85.0,
        positive_ratio=0.8,
        review_count=100,
        last_calculated_at=datetime.now(),
    )
    update_instructor_trust_score(TEST_INSTRUCTOR, data)
    instructor = get_instructor(TEST_INSTRUCTOR)
    assert instructor["trust_score"] == 85.0


def test_get_instructor_returns_data():
    upsert_instructor(TEST_INSTRUCTOR, "inflearn")
    result = get_instructor(TEST_INSTRUCTOR)
    assert result["name"] == TEST_INSTRUCTOR


# ── exams ────────────────────────────────────────────────

def test_upsert_exam_creates_new():
    data = ExamCreate(
        exam_name=TEST_EXAM,
        exam_type="필기",
        exam_date="2026-09-01",
    )
    result = upsert_exam(data)
    assert result is not None


def test_upsert_exam_deduplicates():
    data = ExamCreate(exam_name=TEST_EXAM, exam_type="필기")
    upsert_exam(data)
    upsert_exam(data)
    rows = supabase.table("exams").select("*").eq("exam_name", TEST_EXAM).execute().data
    assert len(rows) == 1


def test_get_exams_keyword_filter():
    upsert_exam(ExamCreate(exam_name=TEST_EXAM, exam_type="필기", exam_date="2026-09-01", d_day=97))
    result = get_exams(keyword="testexam")
    assert any(r["exam_name"] == TEST_EXAM for r in result)


def test_update_exam_dday():
    upsert_exam(ExamCreate(exam_name=TEST_EXAM, exam_type="필기", exam_date="2026-09-01"))
    update_exam_dday()
    rows = supabase.table("exams").select("d_day").eq("exam_name", TEST_EXAM).execute().data
    assert rows[0]["d_day"] is not None


# ── zapier_alerts_log ────────────────────────────────────

def test_log_zapier_alert():
    result = log_zapier_alert("dday", {"exam": TEST_EXAM, "d_day": 7})
    assert result is not None
