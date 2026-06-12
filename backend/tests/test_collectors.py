"""외부 API 수집기 테스트.

실제 네트워크 호출 없이 requests.get 를 모킹해서 검증한다.
"""
from unittest.mock import MagicMock, patch

from app.collectors.naver_api import collect_naver_reviews
from app.db.models import ReviewCreate


def _fake_response(items: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"items": items}
    resp.raise_for_status = MagicMock()
    return resp


_NAVER_ITEMS = [
    {
        "title": "<b>홍길동</b> 강의 진짜 <b>후기</b>",
        "description": "환급까지 받았어요. 설명이 <b>깔끔</b>합니다.   단점도 있음.",
        "link": "https://blog.naver.com/abc/111",
    },
    {
        "title": "에듀윌 공무원 수강 후기",
        "description": "기출 분석이 좋았다",
        "link": "https://blog.naver.com/def/222",
    },
]


def test_collect_naver_reviews_cleans_html_and_wires_insert_review():
    """수집 → clean_text → insert_review() 연결 확인"""
    with patch("app.collectors.naver_api.requests.get", return_value=_fake_response(_NAVER_ITEMS)) as mock_get, \
         patch("app.collectors.naver_api.insert_review") as mock_insert:
        saved = collect_naver_reviews("홍길동")

    # 2건 저장됨
    assert len(saved) == 2
    assert mock_insert.call_count == 2

    first = mock_insert.call_args_list[0].args[0]
    assert isinstance(first, ReviewCreate)
    assert first.platform_source == "naver_blog"
    assert first.instructor_name == "홍길동"
    assert first.original_url == "https://blog.naver.com/abc/111"
    # HTML 태그 제거 + 공백 정규화
    assert "<b>" not in first.content
    assert "홍길동 강의 진짜 후기" in first.content

    # API 파라미터: display/sort 명세대로
    params = mock_get.call_args.kwargs["params"]
    assert params["sort"] == "date"
    assert params["query"] == "홍길동 강의 후기"


def test_collect_naver_reviews_skips_empty_content():
    items = [
        {"title": "", "description": "", "link": "https://blog.naver.com/x/1"},
        {"title": "정상 후기", "description": "내용 있음", "link": "https://blog.naver.com/x/2"},
    ]
    with patch("app.collectors.naver_api.requests.get", return_value=_fake_response(items)), \
         patch("app.collectors.naver_api.insert_review") as mock_insert:
        saved = collect_naver_reviews("김강사")

    assert len(saved) == 1
    assert mock_insert.call_count == 1


def test_collect_naver_reviews_truncates_to_500_chars():
    long_desc = "가" * 600
    items = [{"title": "긴 후기", "description": long_desc, "link": "https://blog.naver.com/x/3"}]
    with patch("app.collectors.naver_api.requests.get", return_value=_fake_response(items)), \
         patch("app.collectors.naver_api.insert_review"):
        saved = collect_naver_reviews("박강사")

    assert len(saved[0].content) <= 500


def test_collect_naver_reviews_api_failure_returns_empty():
    with patch("app.collectors.naver_api.requests.get", side_effect=Exception("401 Unauthorized")), \
         patch("app.collectors.naver_api.insert_review") as mock_insert:
        saved = collect_naver_reviews("홍길동")

    assert saved == []
    mock_insert.assert_not_called()


# ── YouTube 수집기 테스트 (search.list → commentThreads.list) ──────────

from app.collectors.youtube_api import collect_youtube_reviews


def _yt_search_resp(video_ids: list[str]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"items": [{"id": {"videoId": v}} for v in video_ids]}
    return resp


def _yt_comments_resp(comments: list[tuple]) -> MagicMock:
    # comments: [(comment_id, textDisplay), ...]
    items = [
        {"id": cid, "snippet": {"topLevelComment": {"snippet": {"textDisplay": text}}}}
        for cid, text in comments
    ]
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"items": items}
    return resp


def test_collect_youtube_reviews_cleans_and_unique_urls():
    def fake_get(url, params=None, timeout=None):
        if "search" in url:
            return _yt_search_resp(["vid1"])
        return _yt_comments_resp([
            ("c1", "<b>완강</b> 했어요 &quot;강추&quot;<br>설명 좋음"),
            ("c2", "조금 어려웠음"),
        ])

    with patch("app.collectors.youtube_api.requests.get", side_effect=fake_get), \
         patch("app.collectors.youtube_api.insert_review") as mock_insert:
        total = collect_youtube_reviews("홍길동")

    assert total == 2
    assert mock_insert.call_count == 2

    r1 = mock_insert.call_args_list[0].args[0]
    assert isinstance(r1, ReviewCreate)
    assert r1.platform_source == "youtube_comment"
    assert r1.instructor_name == "홍길동"
    assert "<b>" not in r1.content and "<br>" not in r1.content
    assert "완강 했어요" in r1.content

    # 같은 영상이라도 댓글별 original_url 이 고유해야 upsert 충돌이 안 남
    urls = [c.args[0].original_url for c in mock_insert.call_args_list]
    assert urls[0] == "https://www.youtube.com/watch?v=vid1&lc=c1"
    assert urls[1] == "https://www.youtube.com/watch?v=vid1&lc=c2"
    assert len(set(urls)) == 2


def test_collect_youtube_reviews_skips_empty_and_malformed():
    def fake_get(url, params=None, timeout=None):
        if "search" in url:
            return _yt_search_resp(["vid1"])
        # 빈 댓글 + 정상 댓글
        return _yt_comments_resp([("c1", "   "), ("c2", "좋은 강의")])

    with patch("app.collectors.youtube_api.requests.get", side_effect=fake_get), \
         patch("app.collectors.youtube_api.insert_review") as mock_insert:
        total = collect_youtube_reviews("김강사")

    assert total == 1
    assert mock_insert.call_count == 1


def test_collect_youtube_reviews_search_failure_returns_zero():
    with patch("app.collectors.youtube_api.requests.get", side_effect=Exception("403 quota")), \
         patch("app.collectors.youtube_api.insert_review") as mock_insert:
        total = collect_youtube_reviews("홍길동")

    assert total == 0
    mock_insert.assert_not_called()


def test_collect_youtube_reviews_skips_video_without_id():
    def fake_get(url, params=None, timeout=None):
        if "search" in url:
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            # videoId 없는 항목(채널/재생목록 결과 등)
            resp.json.return_value = {"items": [{"id": {}}, {"id": {"videoId": "vidX"}}]}
            return resp
        return _yt_comments_resp([("c1", "댓글")])

    with patch("app.collectors.youtube_api.requests.get", side_effect=fake_get), \
         patch("app.collectors.youtube_api.insert_review") as mock_insert:
        total = collect_youtube_reviews("박강사")

    assert total == 1
    assert mock_insert.call_count == 1


# ── K-MOOC 수집기 테스트 ──────────────────────────────────────────

from app.collectors.kmooc_api import collect_kmooc_lectures
from app.db.models import LectureCreate as _LC


def _kmooc_resp(results: list[dict], next_url=None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"results": results, "pagination": {"next": next_url}}
    return resp


_KMOOC_COURSE = {
    "course_id": "course-v1:KAISTk+CS101+2024",
    "name": "<b>인공지능</b> 입문",
    "org": "KAISTk",
    "media": {"course_image": {"uri": "/asset/ai.jpg"}},
}


def test_collect_kmooc_maps_fields_and_wires_upsert():
    with patch("app.collectors.kmooc_api.requests.get", return_value=_kmooc_resp([_KMOOC_COURSE])), \
         patch("app.collectors.kmooc_api.upsert_lecture") as mock_upsert:
        total = collect_kmooc_lectures()

    assert total == 1
    assert mock_upsert.call_count == 1
    lec = mock_upsert.call_args_list[0].args[0]
    assert isinstance(lec, _LC)
    assert lec.platform == "kmooc"
    assert lec.is_free is True
    assert lec.price == 0
    assert lec.title == "인공지능 입문"          # HTML 제거
    assert lec.instructor_name == "KAISTk"
    # course_id 가 아닌 about 페이지 URL로 구성
    assert lec.url == "https://www.kmooc.kr/courses/course-v1:KAISTk+CS101+2024/about"
    # 상대경로 썸네일 절대화
    assert lec.thumbnail_url == "https://www.kmooc.kr/asset/ai.jpg"


def test_collect_kmooc_follows_pagination():
    page1 = _kmooc_resp([_KMOOC_COURSE], next_url="https://www.kmooc.kr/api/courses/v1/courses/?page=2")
    page2 = _kmooc_resp([{**_KMOOC_COURSE, "course_id": "course-v1:X+Y+Z", "name": "2페이지 강의"}])

    with patch("app.collectors.kmooc_api.requests.get", side_effect=[page1, page2]) as mock_get, \
         patch("app.collectors.kmooc_api.upsert_lecture") as mock_upsert:
        total = collect_kmooc_lectures()

    assert total == 2
    assert mock_get.call_count == 2
    assert mock_upsert.call_count == 2


def test_collect_kmooc_passes_org_filter():
    with patch("app.collectors.kmooc_api.requests.get", return_value=_kmooc_resp([])) as mock_get, \
         patch("app.collectors.kmooc_api.upsert_lecture"):
        collect_kmooc_lectures(org="KAISTk")

    params = mock_get.call_args.kwargs["params"]
    assert params["org"] == "KAISTk"
    assert params["page_size"] == 100


def test_collect_kmooc_skips_empty_title():
    courses = [{"course_id": "c1", "name": ""}, {"course_id": "c2", "name": "정상 강의"}]
    with patch("app.collectors.kmooc_api.requests.get", return_value=_kmooc_resp(courses)), \
         patch("app.collectors.kmooc_api.upsert_lecture") as mock_upsert:
        total = collect_kmooc_lectures()

    assert total == 1
    assert mock_upsert.call_count == 1


def test_collect_kmooc_api_failure_returns_zero():
    with patch("app.collectors.kmooc_api.requests.get", side_effect=Exception("500")), \
         patch("app.collectors.kmooc_api.upsert_lecture") as mock_upsert:
        total = collect_kmooc_lectures()

    assert total == 0
    mock_upsert.assert_not_called()


# ── 큐넷(Q-Net) 수집기 테스트 (XML → 필기/실기 분리) ──────────────────

from app.collectors.qnet_api import collect_qnet_exams
from app.db.models import ExamCreate

_QNET_XML_FULL = """<?xml version="1.0" encoding="UTF-8"?>
<response><body><items>
  <item>
    <jmfldnm>정보처리기사</jmfldnm>
    <docRegStartDt>20240301</docRegStartDt>
    <docRegEndDt>20240305</docRegEndDt>
    <docExamStartDt>20240401</docExamStartDt>
    <docPassDt>20240420</docPassDt>
    <pracRegStartDt>20240501</pracRegStartDt>
    <pracRegEndDt>20240505</pracRegEndDt>
    <pracExamStartDt>20240601</pracExamStartDt>
    <pracPassDt>20240620</pracPassDt>
  </item>
</items></body></response>"""


def _qnet_resp(xml_text: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = xml_text
    return resp


def test_collect_qnet_splits_written_and_practical():
    with patch("app.collectors.qnet_api.requests.get", return_value=_qnet_resp(_QNET_XML_FULL)), \
         patch("app.collectors.qnet_api.upsert_exam") as mock_upsert, \
         patch("app.collectors.qnet_api.update_exam_dday") as mock_dday:
        total = collect_qnet_exams(year=2024)

    assert total == 2
    assert mock_upsert.call_count == 2

    written, practical = (c.args[0] for c in mock_upsert.call_args_list)
    assert isinstance(written, ExamCreate)

    # 필기 행 — YYYYMMDD → ISO 변환 확인
    assert written.exam_name == "정보처리기사"
    assert written.exam_type == "필기"
    assert written.application_start == "2024-03-01"
    assert written.application_end == "2024-03-05"
    assert written.exam_date == "2024-04-01"
    assert written.result_date == "2024-04-20"
    assert written.d_day is None
    assert written.related_keywords == ["정보처리기사"]

    # 실기 행
    assert practical.exam_type == "실기"
    assert practical.application_start == "2024-05-01"
    assert practical.exam_date == "2024-06-01"
    assert practical.result_date == "2024-06-20"

    # 수집 후 d_day 초기 계산 호출
    mock_dday.assert_called_once()


def test_collect_qnet_only_written_when_no_practical():
    xml = """<response><body><items><item>
      <jmfldnm>컴퓨터활용능력</jmfldnm>
      <docRegStartDt>20240101</docRegStartDt>
      <docExamStartDt>20240201</docExamStartDt>
    </item></items></body></response>"""
    with patch("app.collectors.qnet_api.requests.get", return_value=_qnet_resp(xml)), \
         patch("app.collectors.qnet_api.upsert_exam") as mock_upsert, \
         patch("app.collectors.qnet_api.update_exam_dday"):
        total = collect_qnet_exams(year=2024)

    assert total == 1
    assert mock_upsert.call_args_list[0].args[0].exam_type == "필기"


def test_collect_qnet_skips_item_without_name():
    xml = """<response><body><items><item>
      <docExamStartDt>20240201</docExamStartDt>
    </item></items></body></response>"""
    with patch("app.collectors.qnet_api.requests.get", return_value=_qnet_resp(xml)), \
         patch("app.collectors.qnet_api.upsert_exam") as mock_upsert, \
         patch("app.collectors.qnet_api.update_exam_dday"):
        total = collect_qnet_exams(year=2024)

    assert total == 0
    mock_upsert.assert_not_called()


def test_collect_qnet_passes_service_key_and_year():
    with patch("app.collectors.qnet_api.requests.get", return_value=_qnet_resp("<response/>")) as mock_get, \
         patch("app.collectors.qnet_api.upsert_exam"), \
         patch("app.collectors.qnet_api.update_exam_dday"):
        collect_qnet_exams(year=2026)

    params = mock_get.call_args.kwargs["params"]
    assert params["implYy"] == "2026"
    assert "ServiceKey" in params


def test_collect_qnet_api_failure_returns_zero():
    with patch("app.collectors.qnet_api.requests.get", side_effect=Exception("service key error")), \
         patch("app.collectors.qnet_api.upsert_exam") as mock_upsert, \
         patch("app.collectors.qnet_api.update_exam_dday"):
        total = collect_qnet_exams(year=2024)

    assert total == 0
    mock_upsert.assert_not_called()
