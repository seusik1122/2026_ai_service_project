# 인프런 크롤러
# 대상 URL: https://www.inflearn.com/courses?order=rating
# 수집 항목: 강의명, 강사명, 평점, 수강생 수, 가격, 카테고리, 태그, URL, 썸네일
#
# ⚠️ CSS 셀렉터는 라이브 사이트 개발자 도구로 직접 확인이 필요하다.
#    아래 셀렉터는 인프런 코스 카드의 일반적 구조를 기준으로 작성한 값이며,
#    실제 마크업이 바뀌면 _SELECTORS 상수만 수정하면 된다.
import re
from typing import Optional

from bs4 import BeautifulSoup

from app.crawlers.base_crawler import BaseCrawler
from app.utils.logger import logger


class InflearnCrawler(BaseCrawler):
    PLATFORM = "inflearn"
    BASE_URL = "https://www.inflearn.com/courses?order=rating&page={page}"
    MAX_PAGES = 10

    # 셀렉터 모음 (한 곳에서 관리). 명세서 섹션 4에 문서화된 값을 우선 적용하고,
    # 명세에 없는 항목은 라이브 사이트 개발자 도구로 확인이 필요한 placeholder다.
    _SELECTORS = {
        "card": ".course-card-item",                    # 명세서 섹션 4
        "title": ".course-card-item--title",            # 명세서 섹션 4
        "instructor": ".course-card-item--instructors",  # 명세서 섹션 4
        "rating": ".score",                             # 명세서 섹션 4
        "students": ".course-card-item--students",      # ⚠️ 미명세 — 라이브 확인 필요
        "price": ".course-card-item--price",            # ⚠️ 미명세 — 라이브 확인 필요
        "category": ".course-card-item--category",      # ⚠️ 미명세 — 라이브 확인 필요
        "tag": ".tag",                                  # ⚠️ 미명세 — 라이브 확인 필요
        "link": "a",
        "thumbnail": "img",
    }

    async def crawl(self) -> list[dict]:
        """전체 페이지를 순회하며 강의를 수집하고 DB에 저장. 수집 항목 리스트 반환."""
        await self.init_browser()
        collected: list[dict] = []
        try:
            for page_num in range(1, self.MAX_PAGES + 1):
                url = self.BASE_URL.format(page=page_num)
                logger.info(f"인프런 크롤링: {url}")
                html = await self.fetch_page(url, wait_selector=self._SELECTORS["card"])
                if not html:
                    logger.warning(f"인프런 페이지 응답 없음 (page={page_num})")
                    continue
                items = self.parse_lectures(html)
                if not items:
                    logger.info(f"인프런 더 이상 강의 없음 (page={page_num}) — 종료")
                    break
                await self.save_to_db(items)  # → queries.upsert_lecture()
                collected.extend(items)
            logger.info(f"인프런 크롤링 완료: {len(collected)}건")
        finally:
            await self.close()
        return collected

    def parse_lectures(self, html: str) -> list[dict]:
        """목록 페이지 HTML에서 강의 카드들을 파싱해 LectureCreate 호환 dict 리스트 반환."""
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(self._SELECTORS["card"])
        lectures: list[dict] = []
        for card in cards:
            try:
                lecture = self._parse_card(card)
                if lecture and lecture.get("title"):
                    lectures.append(lecture)
            except Exception as e:
                logger.error(f"인프런 카드 파싱 실패 — {e}")
        return lectures

    def _parse_card(self, card) -> dict:
        title = self._text(card, "title")
        instructor = self._text(card, "instructor") or None
        category = self._text(card, "category") or None

        price, is_free = self._parse_price(self._text(card, "price"))
        rating = self._parse_float(self._text(card, "rating"))
        student_count = self._parse_int(self._text(card, "students"))

        link_el = card.select_one(self._SELECTORS["link"])
        url = self._abs_url(link_el.get("href")) if link_el else None

        img_el = card.select_one(self._SELECTORS["thumbnail"])
        thumbnail_url = (img_el.get("src") or img_el.get("data-src")) if img_el else None

        tags = [t.get_text(strip=True) for t in card.select(self._SELECTORS["tag"]) if t.get_text(strip=True)]

        return {
            "platform": self.PLATFORM,
            "title": title,
            "instructor_name": instructor,
            "category": category,
            "price": price,
            "rating": rating,
            "student_count": student_count,
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
    def _parse_price(text: str) -> tuple[int, bool]:
        """'₩99,000' → (99000, False), '무료'/'' → (0, True)"""
        if not text or "무료" in text or "free" in text.lower():
            return 0, True
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return 0, True
        price = int(digits)
        return price, price == 0

    @staticmethod
    def _parse_float(text: str) -> Optional[float]:
        m = re.search(r"\d+(\.\d+)?", text or "")
        return float(m.group()) if m else None

    @staticmethod
    def _parse_int(text: str) -> Optional[int]:
        digits = re.sub(r"[^\d]", "", text or "")
        return int(digits) if digits else None

    @staticmethod
    def _abs_url(href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        if href.startswith("http"):
            return href
        return f"https://www.inflearn.com{href}"
