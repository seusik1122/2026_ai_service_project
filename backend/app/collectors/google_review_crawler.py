"""
네이버 검색으로 강의/강사 후기 수집.
막힌 사이트(클래스101, 패스트캠퍼스, Udemy 등) 후기를 블로그에서 수집.
"""
import re
import asyncio
import random
from typing import Optional
from playwright.async_api import async_playwright
from app.db.queries import upsert_instructor, insert_review
from app.db.models import ReviewCreate
from app.utils.logger import logger

SEARCH_TARGETS = [
    ("패스트캠퍼스 전한길 한국사 수강후기", "전한길", "fastcampus"),
    ("패스트캠퍼스 신용한 행정학 수강후기", "신용한", "fastcampus"),
    ("패스트캠퍼스 파이썬 강의 수강후기 솔직", None, "fastcampus"),
    ("패스트캠퍼스 부트캠프 후기 솔직", None, "fastcampus"),
    ("클래스101 강의 솔직후기 추천", None, "class101"),
    ("클래스101 드로잉 수강후기", None, "class101"),
    ("유데미 파이썬 강의 후기 추천", None, "udemy"),
    ("유데미 강의 솔직 후기 추천", None, "udemy"),
    ("Udemy 강의 한국어 후기", None, "udemy"),
    ("유데미 웹개발 부트캠프 후기", None, "udemy"),
    ("인프런 김영한 스프링 수강후기", "김영한", "inflearn"),
    ("인프런 나동빈 알고리즘 강의 후기", "나동빈", "inflearn"),
    ("해커스 토익 강의 솔직후기", None, "hackers"),
    ("시원스쿨 영어 수강후기 솔직", "이시원", "siwonschool"),
    ("에듀윌 공무원 수강후기", None, "eduwill"),
    ("노마드코더 강의 후기 추천", "니꼬쌤", "nomadcoder"),
]

SKIP_DOMAINS = [
    "fastcampus.co.kr", "class101.net", "inflearn.com",
    "hackers.com", "siwonschool.com", "eduwill.net",
    "naver.com/search", "google.com", "youtube.com",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class GoogleReviewCrawler:
    """네이버 블로그/카페 검색으로 강의 후기 수집."""

    MAX_RESULTS_PER_QUERY = 5
    MIN_CONTENT_LENGTH = 150

    async def crawl(self) -> int:
        total = 0
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                for keyword, instructor_name, platform in SEARCH_TARGETS:
                    count = await self._search_and_collect(browser, keyword, instructor_name, platform)
                    total += count
                    logger.info(f"[후기수집] '{keyword}': {count}건")
                    await asyncio.sleep(random.uniform(5, 10))
            finally:
                await browser.close()

        logger.info(f"[후기수집] 전체 완료: {total}건")
        return total

    async def _search_and_collect(
        self, browser, keyword: str, instructor_name: Optional[str], platform: str
    ) -> int:
        page = await browser.new_page(user_agent=random.choice(USER_AGENTS))
        collected = 0
        try:
            url = f"https://search.naver.com/search.naver?query={keyword.replace(' ', '+')}&where=blog"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(random.uniform(2000, 3000))

            # 검색 결과에서 외부 블로그 링크 수집
            links = await page.query_selector_all("a")
            blog_urls = []
            seen = set()
            for link in links:
                href = await link.get_attribute("href")
                if not href or href in seen:
                    continue
                if not href.startswith("http"):
                    continue
                if any(d in href for d in SKIP_DOMAINS):
                    continue
                # 실제 콘텐츠 링크 (짧은 건 광고/메뉴)
                text = (await link.inner_text()).strip()
                if len(text) > 8:
                    seen.add(href)
                    blog_urls.append(href)

            for blog_url in blog_urls[:self.MAX_RESULTS_PER_QUERY]:
                text = await self._fetch_content(page, blog_url)
                if text and len(text) >= self.MIN_CONTENT_LENGTH:
                    self._save(text, blog_url, instructor_name, platform)
                    collected += 1
                await asyncio.sleep(random.uniform(1, 3))

        except Exception as e:
            logger.error(f"[후기수집] 검색 실패 '{keyword}': {e}")
        finally:
            await page.close()
        return collected

    async def _fetch_content(self, page, url: str) -> Optional[str]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1500)

            for sel in [
                ".se-main-container",   # 네이버 블로그 스마트에디터
                "#postViewArea",        # 네이버 블로그 구형
                ".article-view",        # 티스토리
                ".entry-content",       # 티스토리/워드프레스
                ".post-content",        # velog/브런치
                "article",
                "main",
            ]:
                el = await page.query_selector(sel)
                if el:
                    text = self._clean(await el.inner_text())
                    if len(text) >= self.MIN_CONTENT_LENGTH:
                        return text[:1500]

            body = await page.query_selector("body")
            if body:
                return self._clean(await body.inner_text())[:1500]
        except Exception as e:
            logger.warning(f"[후기수집] 본문 수집 실패 {url[:60]}: {e}")
        return None

    def _save(self, content: str, source_url: str, instructor_name: Optional[str], platform: str):
        try:
            if not instructor_name:
                instructor_name = self._extract_instructor(content)
            if instructor_name:
                upsert_instructor(instructor_name, platform)
            insert_review(ReviewCreate(
                instructor_name=instructor_name,
                platform_source=f"blog_{platform}",
                content=content,
                original_url=source_url,
            ))
        except Exception as e:
            logger.error(f"[후기수집] DB 저장 실패: {e}")

    @staticmethod
    def _extract_instructor(text: str) -> Optional[str]:
        for name in ["김영한", "박재성", "조코딩", "이고잉", "나동빈", "니꼬쌤",
                     "전한길", "신용한", "이선재", "이시원", "수제비", "드림코딩"]:
            if name in text:
                return name
        return None

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        return text.strip()
