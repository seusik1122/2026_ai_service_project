# 클래스101 크롤러
# 대상 URL: https://class101.net/ko/categories
# 주의: 가격 / 수강생 수는 로그인해야 노출됨 → 비공개값은 price=-1, student_count=None 처리
#       (price=-1 은 '무료'(0)와 구분되는 '미수집/비공개' sentinel)
#
# ⚠️ CSS 셀렉터는 라이브 사이트 개발자 도구로 직접 확인이 필요하다.
#    실제 마크업이 바뀌면 _SELECTORS 상수만 수정하면 된다.
import re
from typing import Optional

from bs4 import BeautifulSoup

from app.crawlers.base_crawler import BaseCrawler
from app.utils.logger import logger


def parse_lecture_price(price_text: str) -> tuple[int, bool]:
    """가격 텍스트 파싱 → (price, is_free).

    로그인 필요/미수집 등 비공개 시 (-1, False) 반환 (price=-1 = 비공개 sentinel).
    클래스101은 유료 플랫폼이라 is_free 는 정상값에서도 False.
    """
    if not price_text or "로그인" in price_text or "원" not in price_text:
        return -1, False
    digits = re.sub(r"[^\d]", "", price_text)
    if not digits:
        return -1, False
    return int(digits), False


class Class101Crawler(BaseCrawler):
    PLATFORM = "class101"
    BASE_URL = "https://class101.net/ko/categories"

    _SELECTORS = {
        "card": "div.product_card",
        "title": ".product_title",
        "instructor": ".creator",
        "category": ".category",
        "price": ".price",
        "tag": ".tag",
        "link": "a",
        "thumbnail": "img",
    }

    async def crawl(self) -> list[dict]:
        """카테고리 페이지를 수집해 DB에 저장. 수집 항목 리스트 반환."""
        await self.init_browser()
        collected: list[dict] = []
        try:
            logger.info(f"클래스101 크롤링 시작: {self.BASE_URL}")
            html = await self.fetch_page(self.BASE_URL, wait_selector=self._SELECTORS["card"])
            if not html:
                logger.warning("클래스101 페이지 응답 없음")
                return collected
            items = self.parse_lectures(html)
            if items:
                await self.save_to_db(items)  # → queries.upsert_lecture()
                collected.extend(items)
            logger.info(f"클래스101 크롤링 완료: {len(collected)}건")
        finally:
            await self.close()
        return collected

    def parse_lectures(self, html: str) -> list[dict]:
        """목록 HTML에서 강의 카드들을 파싱해 LectureCreate 호환 dict 리스트 반환."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(self._SELECTORS["card"])
        lectures: list[dict] = []
        for card in cards:
            try:
                lecture = self._parse_card(card)
                if lecture and lecture.get("title"):
                    lectures.append(lecture)
            except Exception as e:
                logger.error(f"클래스101 카드 파싱 실패 — {e}")
        return lectures

    def _parse_card(self, card) -> dict:
        price, is_free = parse_lecture_price(self._text(card, "price"))

        link_el = card.select_one(self._SELECTORS["link"])
        url = self._abs_url(link_el.get("href")) if link_el else None

        img_el = card.select_one(self._SELECTORS["thumbnail"])
        thumbnail_url = (img_el.get("src") or img_el.get("data-src")) if img_el else None

        tags = [t.get_text(strip=True) for t in card.select(self._SELECTORS["tag"]) if t.get_text(strip=True)]

        return {
            "platform": self.PLATFORM,
            "title": self._text(card, "title"),
            "instructor_name": self._text(card, "instructor") or None,
            "category": self._text(card, "category") or None,
            "price": price,
            "rating": None,            # 비로그인 미수집
            "student_count": None,     # 로그인 필요 → 미수집
            "url": url,
            "thumbnail_url": thumbnail_url,
            "tags": tags or None,
            "is_free": is_free,
        }

    # ── 파싱 헬퍼 ────────────────────────────────────────────

    def _text(self, card, key: str) -> str:
        el = card.select_one(self._SELECTORS[key])
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _abs_url(href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        if href.startswith("http"):
            return href
        return f"https://class101.net{href}"
