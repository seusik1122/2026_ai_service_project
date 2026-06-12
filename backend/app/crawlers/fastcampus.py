# 패스트캠퍼스 크롤러
# 대상 URL: https://fastcampus.co.kr/categories
# 방식: requests + BeautifulSoup (SSR 페이지라 Playwright 불필요 — 명세서 섹션 4)
# 수집 항목: 강의명, 강사명, 가격, 카테고리, 태그, URL (평점/수강생수/썸네일은 미수집)
#
# 백엔드 규칙(모든 크롤러는 BaseCrawler 상속)을 지키기 위해 BaseCrawler를 상속하되,
# Playwright 대신 requests 를 쓰도록 fetch_page 만 오버라이드한다.
# 랜덤 User-Agent / 실패 시 3회 재시도 / queries.upsert_lecture 저장 규칙은 유지.
#
# ⚠️ CSS 셀렉터는 라이브 사이트 개발자 도구로 직접 확인이 필요하다.
import asyncio
import random
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.crawlers.base_crawler import BaseCrawler
from app.utils.logger import logger


class FastcampusCrawler(BaseCrawler):
    PLATFORM = "fastcampus"
    BASE_URL = "https://fastcampus.co.kr/categories"
    TIMEOUT = 10  # requests 타임아웃(초)

    # ⚠️ 명세서에 패스트캠퍼스 셀렉터는 없음 — 라이브 확인 필요한 placeholder
    _SELECTORS = {
        "card": ".course-card",
        "title": ".course-card__title",
        "instructor": ".course-card__instructor",
        "category": ".course-card__category",
        "price": ".course-card__price",
        "tag": ".course-card__tag",
        "link": "a",
    }

    async def crawl(self) -> list[dict]:
        """SSR 카테고리 페이지를 수집해 DB에 저장. 수집 항목 리스트 반환."""
        collected: list[dict] = []
        logger.info(f"패스트캠퍼스 크롤링 시작: {self.BASE_URL}")
        html = await self.fetch_page(self.BASE_URL)
        if not html:
            logger.warning("패스트캠퍼스 페이지 응답 없음")
            return collected
        items = self.parse_lectures(html)
        if items:
            await self.save_to_db(items)  # → queries.upsert_lecture()
            collected.extend(items)
        logger.info(f"패스트캠퍼스 크롤링 완료: {len(collected)}건")
        return collected

    async def fetch_page(
        self,
        url: str,
        retries: Optional[int] = None,
        wait_selector: Optional[str] = None,  # SSR이라 JS 셀렉터 대기 불필요 — 시그니처 호환용
        timeout: Optional[int] = None,
    ) -> str:
        """requests 로 SSR HTML 수집. 실패 시 최대 retries회 재시도 후 빈 문자열 반환."""
        attempts = retries if retries is not None else self.MAX_RETRIES
        for attempt in range(1, attempts + 1):
            try:
                html = await asyncio.to_thread(self._get, url)
                await asyncio.sleep(random.uniform(1, 3))  # 반탐지 딜레이
                return html
            except Exception as e:
                if attempt < attempts:
                    logger.warning(f"fetch_page 재시도 {attempt}/{attempts}: {url} — {e}")
                    await asyncio.sleep(random.uniform(1, 3))
                else:
                    logger.error(f"fetch_page 실패 ({attempts}회 시도): {url} — {e}")
        return ""

    def _get(self, url: str) -> str:
        """동기 requests 호출 (asyncio.to_thread 로 구동)."""
        resp = requests.get(
            url,
            headers={"User-Agent": self.ua.random},
            timeout=self.TIMEOUT,
        )
        resp.raise_for_status()
        return resp.text

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
                logger.error(f"패스트캠퍼스 카드 파싱 실패 — {e}")
        return lectures

    def _parse_card(self, card) -> dict:
        price, is_free = self._parse_price(self._text(card, "price"))

        link_el = card.select_one(self._SELECTORS["link"])
        url = self._abs_url(link_el.get("href")) if link_el else None

        tags = [t.get_text(strip=True) for t in card.select(self._SELECTORS["tag"]) if t.get_text(strip=True)]

        return {
            "platform": self.PLATFORM,
            "title": self._text(card, "title"),
            "instructor_name": self._text(card, "instructor") or None,
            "category": self._text(card, "category") or None,
            "price": price,
            "rating": None,          # 미수집(명세 항목 아님)
            "student_count": None,   # 미수집(명세 항목 아님)
            "url": url,
            "thumbnail_url": None,   # 미수집(명세 항목 아님)
            "tags": tags or None,
            "is_free": is_free,
        }

    # ── 파싱 헬퍼 ────────────────────────────────────────────

    def _text(self, card, key: str) -> str:
        el = card.select_one(self._SELECTORS[key])
        return el.get_text(strip=True) if el else ""

    @staticmethod
    def _parse_price(text: str) -> tuple[int, bool]:
        """'599,000원' → (599000, False), '무료'/'' → (0, True)"""
        if not text or "무료" in text or "free" in text.lower():
            return 0, True
        digits = re.sub(r"[^\d]", "", text)
        if not digits:
            return 0, True
        price = int(digits)
        return price, price == 0

    @staticmethod
    def _abs_url(href: Optional[str]) -> Optional[str]:
        if not href:
            return None
        if href.startswith("http"):
            return href
        return f"https://fastcampus.co.kr{href}"
