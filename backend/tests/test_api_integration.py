"""
FastAPI 엔드포인트 통합 테스트.
실제 서버(http://localhost:8000)에 HTTP 요청을 보내 응답을 검증한다.

실행 방법:
    1. 터미널 A: uvicorn main:app --reload
    2. 터미널 B: pytest tests/test_api_integration.py -v
"""
import pytest
import requests

BASE_URL = "http://localhost:8000"
HEADERS = {"X-API-Key": "my-secret-1234"}


def _get(path: str, params: dict = None) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=10)


def _post(path: str, body: dict) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=body, timeout=10)


# ── 서버 상태 ─────────────────────────────────────────────

def test_health_check():
    """API 키 없이 /health 접근 가능해야 한다."""
    res = requests.get(f"{BASE_URL}/health", timeout=5)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_unauthorized_without_api_key():
    """/api/* 경로는 API 키 없으면 401."""
    res = requests.get(f"{BASE_URL}/api/lectures", timeout=5)
    assert res.status_code == 401


def test_swagger_docs_accessible():
    """/docs는 API 키 없이 접근 가능해야 한다."""
    res = requests.get(f"{BASE_URL}/docs", timeout=5)
    assert res.status_code == 200


# ── GET /api/lectures ────────────────────────────────────

def test_get_lectures_returns_list():
    res = _get("/api/lectures")
    assert res.status_code == 200
    body = res.json()
    assert "lectures" in body
    assert "total" in body
    assert isinstance(body["lectures"], list)


def test_get_lectures_total_matches_list_length():
    res = _get("/api/lectures")
    body = res.json()
    assert body["total"] == len(body["lectures"])


def test_get_lectures_keyword_filter():
    res = _get("/api/lectures", params={"keyword": "파이썬"})
    assert res.status_code == 200
    body = res.json()
    for lecture in body["lectures"]:
        assert "파이썬" in lecture["title"].lower() or "파이썬" in lecture.get("title", "")


def test_get_lectures_is_free_filter():
    res = _get("/api/lectures", params={"is_free": "true"})
    assert res.status_code == 200
    for lecture in res.json()["lectures"]:
        assert lecture["is_free"] is True


def test_get_lectures_platform_filter():
    res = _get("/api/lectures", params={"platform": "inflearn"})
    assert res.status_code == 200
    for lecture in res.json()["lectures"]:
        assert lecture["platform"] == "inflearn"


def test_get_lectures_sort_by_rating():
    res = _get("/api/lectures", params={"sort": "rating", "limit": 5})
    assert res.status_code == 200
    ratings = [l["rating"] for l in res.json()["lectures"] if l.get("rating") is not None]
    assert ratings == sorted(ratings, reverse=True)


def test_get_lectures_limit():
    res = _get("/api/lectures", params={"limit": 3})
    assert res.status_code == 200
    assert len(res.json()["lectures"]) <= 3


# ── GET /api/instructors/{name} ──────────────────────────

def test_get_instructor_not_found():
    res = _get("/api/instructors/존재하지않는강사xyz")
    assert res.status_code == 404


def test_get_instructor_found_has_required_fields():
    """강사가 DB에 존재할 경우 필수 필드를 포함해야 한다."""
    # DB에 있는 첫 번째 강사 이름을 가져와서 테스트
    lectures = _get("/api/lectures", params={"limit": 10}).json()["lectures"]
    instructor_name = next(
        (l["instructor_name"] for l in lectures if l.get("instructor_name")),
        None,
    )
    if instructor_name is None:
        pytest.skip("DB에 강사 데이터 없음")

    res = _get(f"/api/instructors/{instructor_name}")
    assert res.status_code == 200
    body = res.json()
    assert "name" in body
    assert "recent_reviews" in body
    assert isinstance(body["recent_reviews"], list)


# ── GET /api/instructors/trend ───────────────────────────

def test_get_instructor_trend_returns_list():
    res = _get("/api/instructors/trend")
    assert res.status_code == 200
    body = res.json()
    assert "instructors" in body
    assert isinstance(body["instructors"], list)


def test_get_instructor_trend_custom_threshold():
    res = _get("/api/instructors/trend", params={"threshold": 5.0})
    assert res.status_code == 200


# ── GET /api/reviews/{instructor_name} ──────────────────

def test_get_reviews_unknown_instructor_returns_empty():
    res = _get("/api/reviews/존재하지않는강사xyz")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 0
    assert body["reviews"] == []


def test_get_reviews_total_matches_list():
    lectures = _get("/api/lectures", params={"limit": 10}).json()["lectures"]
    instructor_name = next(
        (l["instructor_name"] for l in lectures if l.get("instructor_name")),
        None,
    )
    if instructor_name is None:
        pytest.skip("DB에 강사 데이터 없음")

    res = _get(f"/api/reviews/{instructor_name}")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == len(body["reviews"])


# ── GET /api/exams ───────────────────────────────────────

def test_get_exams_returns_list():
    res = _get("/api/exams")
    assert res.status_code == 200
    body = res.json()
    assert "exams" in body
    assert isinstance(body["exams"], list)


def test_get_exams_d_day_filter():
    res = _get("/api/exams", params={"d_day_within": 90})
    assert res.status_code == 200
    for exam in res.json()["exams"]:
        assert exam["d_day"] is not None
        assert 0 <= exam["d_day"] <= 90


def test_get_exams_keyword_filter():
    res = _get("/api/exams", params={"keyword": "정보"})
    assert res.status_code == 200
    for exam in res.json()["exams"]:
        assert "정보" in exam["exam_name"]


# ── POST /api/zapier/trigger ─────────────────────────────

def test_zapier_trigger_new_lecture():
    res = _post("/api/zapier/trigger", {
        "event_type": "new_lecture",
        "data": {"title": "통합테스트 강의", "platform": "inflearn"},
    })
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["event_type"] == "new_lecture"


def test_zapier_trigger_dday_alert():
    res = _post("/api/zapier/trigger", {
        "event_type": "dday_alert",
        "data": {"exam_name": "정보처리기사", "d_day": 7},
    })
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_zapier_trigger_review_spike():
    res = _post("/api/zapier/trigger", {
        "event_type": "review_spike",
        "data": {"instructor_name": "테스트강사", "change": 15.0},
    })
    assert res.status_code == 200


def test_zapier_trigger_unknown_event_still_returns_ok():
    """알 수 없는 event_type은 웹훅 전송 없이 로그만 남기고 200 반환."""
    res = _post("/api/zapier/trigger", {
        "event_type": "unknown_event",
        "data": {},
    })
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
