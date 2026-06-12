"""base_crawler.py fetch_page() 모킹 테스트.

실제 브라우저/네트워크 없이 BaseCrawler.fetch_page의 동작을 검증한다.
async 코드는 asyncio.run()으로 구동하므로 pytest-asyncio 의존성이 필요 없다.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crawlers.base_crawler import BaseCrawler
from app.crawlers.inflearn import InflearnCrawler
from app.db.models import LectureCreate


def _make_crawler() -> BaseCrawler:
    """UserAgent 네트워크 의존성을 제거한 BaseCrawler 인스턴스 생성"""
    with patch("app.crawlers.base_crawler.UserAgent") as MockUA:
        MockUA.return_value.random = "test-agent"
        return BaseCrawler()


def _attach_browser(crawler: BaseCrawler, page: AsyncMock) -> MagicMock:
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    crawler.browser = browser
    return browser


def test_fetch_page_success_returns_html():
    crawler = _make_crawler()
    page = AsyncMock()
    page.content.return_value = "<html>ok</html>"
    browser = _attach_browser(crawler, page)

    with patch("app.crawlers.base_crawler.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(crawler.fetch_page("https://example.com"))

    assert result == "<html>ok</html>"
    assert browser.new_page.await_count == 1
    page.close.assert_awaited()


def test_fetch_page_retries_three_times_then_returns_empty():
    crawler = _make_crawler()
    page = AsyncMock()
    page.goto.side_effect = Exception("boom")
    browser = _attach_browser(crawler, page)

    with patch("app.crawlers.base_crawler.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(crawler.fetch_page("https://example.com", retries=3))

    # 3회 모두 실패 → 빈 문자열, 페이지는 매 시도마다 새로 열고 닫음
    assert result == ""
    assert browser.new_page.await_count == 3
    assert page.close.await_count == 3


def test_fetch_page_succeeds_on_second_attempt():
    crawler = _make_crawler()
    page = AsyncMock()
    page.goto.side_effect = [Exception("first fail"), None]
    page.content.return_value = "<html>recovered</html>"
    browser = _attach_browser(crawler, page)

    with patch("app.crawlers.base_crawler.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(crawler.fetch_page("https://example.com", retries=3))

    assert result == "<html>recovered</html>"
    assert browser.new_page.await_count == 2


def test_fetch_page_without_browser_raises():
    crawler = _make_crawler()
    with pytest.raises(RuntimeError):
        asyncio.run(crawler.fetch_page("https://example.com"))


def test_fetch_page_uses_domcontentloaded_and_waits_for_selector():
    crawler = _make_crawler()
    page = AsyncMock()
    page.content.return_value = "<html>cards</html>"
    _attach_browser(crawler, page)

    with patch("app.crawlers.base_crawler.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(crawler.fetch_page("https://example.com", wait_selector=".card"))

    assert result == "<html>cards</html>"
    # SPA 대응: networkidle 이 아니라 domcontentloaded 로 진입
    assert page.goto.call_args.kwargs["wait_until"] == "domcontentloaded"
    # 핵심 셀렉터 렌더 대기 호출 확인
    page.wait_for_selector.assert_awaited_once()
    assert page.wait_for_selector.call_args.args[0] == ".card"


def test_fetch_page_skips_selector_wait_when_not_given():
    crawler = _make_crawler()
    page = AsyncMock()
    page.content.return_value = "<html>ok</html>"
    _attach_browser(crawler, page)

    with patch("app.crawlers.base_crawler.asyncio.sleep", new=AsyncMock()):
        asyncio.run(crawler.fetch_page("https://example.com"))

    page.wait_for_selector.assert_not_awaited()


# ── InflearnCrawler 파싱 + upsert_lecture 연결 테스트 ──────────────

# 명세서 섹션 4의 인프런 셀렉터(.course-card-item / --title / --instructors / .score) 기준
_SAMPLE_HTML = """
<ul>
  <li class="course-card-item">
    <a href="/course/python-intro">
      <img src="https://cdn.inflearn.com/python.png"/>
      <span class="course-card-item--category">개발·프로그래밍</span>
      <p class="course-card-item--title">파이썬 입문</p>
      <span class="course-card-item--instructors">홍길동</span>
      <span class="score">4.9</span>
      <span class="course-card-item--students">1,234명</span>
      <span class="course-card-item--price">₩99,000</span>
      <span class="tag">python</span>
      <span class="tag">basic</span>
    </a>
  </li>
  <li class="course-card-item">
    <a href="https://www.inflearn.com/course/free-git">
      <img data-src="https://cdn.inflearn.com/git.png"/>
      <span class="course-card-item--category">개발·프로그래밍</span>
      <p class="course-card-item--title">무료 Git 특강</p>
      <span class="course-card-item--instructors">김코딩</span>
      <span class="score">4.5</span>
      <span class="course-card-item--students">5,000명</span>
      <span class="course-card-item--price">무료</span>
    </a>
  </li>
</ul>
"""


def test_inflearn_parse_lectures_extracts_fields():
    crawler = _make_crawler_inflearn()
    items = crawler.parse_lectures(_SAMPLE_HTML)

    assert len(items) == 2
    paid, free = items

    assert paid["platform"] == "inflearn"
    assert paid["title"] == "파이썬 입문"
    assert paid["instructor_name"] == "홍길동"
    assert paid["category"] == "개발·프로그래밍"
    assert paid["price"] == 99000
    assert paid["is_free"] is False
    assert paid["rating"] == 4.9
    assert paid["student_count"] == 1234
    assert paid["url"] == "https://www.inflearn.com/course/python-intro"
    assert paid["thumbnail_url"] == "https://cdn.inflearn.com/python.png"
    assert paid["tags"] == ["python", "basic"]

    # 무료 강의 + 절대 URL + data-src 썸네일 처리
    assert free["price"] == 0
    assert free["is_free"] is True
    assert free["url"] == "https://www.inflearn.com/course/free-git"
    assert free["thumbnail_url"] == "https://cdn.inflearn.com/git.png"


def test_inflearn_parsed_items_are_valid_lecture_create():
    crawler = _make_crawler_inflearn()
    for item in crawler.parse_lectures(_SAMPLE_HTML):
        # LectureCreate 스키마 검증 통과해야 함 (예외 발생하지 않음)
        LectureCreate(**item)


def test_inflearn_save_to_db_calls_upsert_lecture():
    """parse → save_to_db → queries.upsert_lecture() 연결 확인"""
    crawler = _make_crawler_inflearn()
    items = crawler.parse_lectures(_SAMPLE_HTML)

    with patch("app.crawlers.base_crawler.upsert_lecture") as mock_upsert:
        asyncio.run(crawler.save_to_db(items))

    assert mock_upsert.call_count == 2
    first_arg = mock_upsert.call_args_list[0].args[0]
    assert isinstance(first_arg, LectureCreate)
    assert first_arg.title == "파이썬 입문"
    assert first_arg.platform == "inflearn"


def _make_crawler_inflearn() -> InflearnCrawler:
    with patch("app.crawlers.base_crawler.UserAgent") as MockUA:
        MockUA.return_value.random = "test-agent"
        return InflearnCrawler()


# ── Class101Crawler 파싱 (price=-1 비공개 처리) 테스트 ─────────────

from app.crawlers.class101 import Class101Crawler, parse_lecture_price

_C101_HTML = """
<div>
  <div class="product_card">
    <a href="/ko/products/abc123">
      <img src="https://cdn.class101.net/abc.png"/>
      <span class="category">드로잉</span>
      <p class="product_title">아이패드 드로잉 클래스</p>
      <span class="creator">박작가</span>
      <span class="price">로그인 후 확인</span>
      <span class="tag">ipad</span>
    </a>
  </div>
  <div class="product_card">
    <a href="https://class101.net/ko/products/def456">
      <img data-src="https://cdn.class101.net/def.png"/>
      <span class="category">요리</span>
      <p class="product_title">홈쿡 마스터</p>
      <span class="creator">김셰프</span>
      <span class="price">129,000원</span>
    </a>
  </div>
</div>
"""


def test_parse_lecture_price_login_required_returns_minus_one():
    assert parse_lecture_price("로그인 후 확인") == (-1, False)
    assert parse_lecture_price("") == (-1, False)
    assert parse_lecture_price("무료") == (-1, False)  # '원' 없음 → 비공개 처리
    assert parse_lecture_price("129,000원") == (129000, False)


def test_class101_parse_lectures_locked_and_priced():
    crawler = _make_crawler_class101()
    items = crawler.parse_lectures(_C101_HTML)

    assert len(items) == 2
    locked, priced = items

    # 로그인 필요 → price=-1, student_count/rating 미수집
    assert locked["platform"] == "class101"
    assert locked["title"] == "아이패드 드로잉 클래스"
    assert locked["instructor_name"] == "박작가"
    assert locked["price"] == -1
    assert locked["is_free"] is False
    assert locked["student_count"] is None
    assert locked["rating"] is None
    assert locked["url"] == "https://class101.net/ko/products/abc123"
    assert locked["thumbnail_url"] == "https://cdn.class101.net/abc.png"
    assert locked["tags"] == ["ipad"]

    assert priced["price"] == 129000
    assert priced["url"] == "https://class101.net/ko/products/def456"


def test_class101_parsed_items_valid_and_upsert_wiring():
    crawler = _make_crawler_class101()
    items = crawler.parse_lectures(_C101_HTML)
    for item in items:
        LectureCreate(**item)  # 스키마 검증 (price=-1 허용)

    with patch("app.crawlers.base_crawler.upsert_lecture") as mock_upsert:
        asyncio.run(crawler.save_to_db(items))
    assert mock_upsert.call_count == 2
    assert mock_upsert.call_args_list[0].args[0].price == -1


def _make_crawler_class101() -> Class101Crawler:
    with patch("app.crawlers.base_crawler.UserAgent") as MockUA:
        MockUA.return_value.random = "test-agent"
        return Class101Crawler()


# ── FastcampusCrawler (requests + BeautifulSoup) 테스트 ──────────────

from app.crawlers.fastcampus import FastcampusCrawler

_FC_HTML = """
<div>
  <div class="course-card">
    <a href="/dev/data-engineering">
      <span class="course-card__category">데이터</span>
      <p class="course-card__title">데이터 엔지니어링 올인원</p>
      <span class="course-card__instructor">이데이터</span>
      <span class="course-card__price">599,000원</span>
      <span class="course-card__tag">SQL</span>
      <span class="course-card__tag">Airflow</span>
    </a>
  </div>
  <div class="course-card">
    <a href="https://fastcampus.co.kr/free/intro">
      <span class="course-card__category">입문</span>
      <p class="course-card__title">무료 코딩 입문</p>
      <span class="course-card__instructor">김강사</span>
      <span class="course-card__price">무료</span>
    </a>
  </div>
</div>
"""


def _make_crawler_fastcampus() -> FastcampusCrawler:
    with patch("app.crawlers.base_crawler.UserAgent") as MockUA:
        MockUA.return_value.random = "test-agent"
        return FastcampusCrawler()


def test_fastcampus_parse_lectures_fields():
    crawler = _make_crawler_fastcampus()
    items = crawler.parse_lectures(_FC_HTML)

    assert len(items) == 2
    paid, free = items

    assert paid["platform"] == "fastcampus"
    assert paid["title"] == "데이터 엔지니어링 올인원"
    assert paid["instructor_name"] == "이데이터"
    assert paid["category"] == "데이터"
    assert paid["price"] == 599000
    assert paid["is_free"] is False
    assert paid["tags"] == ["SQL", "Airflow"]
    assert paid["url"] == "https://fastcampus.co.kr/dev/data-engineering"
    # 명세 항목 아닌 값은 미수집(None)
    assert paid["rating"] is None
    assert paid["student_count"] is None
    assert paid["thumbnail_url"] is None

    assert free["price"] == 0
    assert free["is_free"] is True
    assert free["url"] == "https://fastcampus.co.kr/free/intro"


def test_fastcampus_parsed_items_valid_and_upsert_wiring():
    crawler = _make_crawler_fastcampus()
    items = crawler.parse_lectures(_FC_HTML)
    for item in items:
        LectureCreate(**item)

    with patch("app.crawlers.base_crawler.upsert_lecture") as mock_upsert:
        asyncio.run(crawler.save_to_db(items))
    assert mock_upsert.call_count == 2
    assert mock_upsert.call_args_list[0].args[0].platform == "fastcampus"


def test_fastcampus_fetch_page_uses_requests_success():
    crawler = _make_crawler_fastcampus()
    resp = MagicMock()
    resp.text = "<html>fc</html>"
    resp.raise_for_status = MagicMock()

    with patch("app.crawlers.fastcampus.requests.get", return_value=resp) as mock_get, \
         patch("app.crawlers.fastcampus.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(crawler.fetch_page("https://fastcampus.co.kr/categories"))

    assert result == "<html>fc</html>"
    assert mock_get.call_count == 1
    # 랜덤 User-Agent 헤더 전달 확인
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == "test-agent"


def test_fastcampus_fetch_page_retries_three_times():
    crawler = _make_crawler_fastcampus()
    with patch("app.crawlers.fastcampus.requests.get", side_effect=Exception("net down")) as mock_get, \
         patch("app.crawlers.fastcampus.asyncio.sleep", new=AsyncMock()):
        result = asyncio.run(crawler.fetch_page("https://fastcampus.co.kr/categories", retries=3))

    assert result == ""
    assert mock_get.call_count == 3
